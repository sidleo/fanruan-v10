"""可手算的 CPT 变换向量；不使用 Java、实例配置或真实网络。"""

import json
import random

import pytest
from click.testing import CliRunner

from frcli import cptmodel, cpttransform, cptxml, reportops
from frcli.commands import report as commands
from frcli.exceptions import ApiError, TemplateValidationError


def cell(at, value=None, formula=None, **kwargs):
    return cptxml.cell_xml(*cptxml.parse_a1(at), value=value, formula=formula, **kwargs)


def sheet(cells="", name="main", extra="", poly=False):
    cls = "PolyWorkSheet" if poly else "WorkSheet"
    grid = ("<RowHeight defaultValue='442000'><![CDATA[442000,884000,1326000,1768000]]></RowHeight>"
            "<ColumnWidth defaultValue='2808000'><![CDATA[2808000,5616000,8424000,11232000]]></ColumnWidth>"
            "<CellElementList>" + cells + "</CellElementList>" + extra)
    return f'<Report class="com.fr.report.worksheet.{cls}" name="{name}">' + grid + '</Report>'


def book(cells="", extra="", others="", main=None):
    return ('\ufeff<?xml version="1.0" encoding="UTF-8"?>\n<WorkBook><!-- untouched A1 -->'
            '<TableDataMap><TableData name="ds" class="com.fr.data.impl.DBTableData">'
            '<Query><![CDATA[select \'C3\' as v]]></Query></TableData></TableDataMap>'
            + (main if main is not None else sheet(cells, extra=extra)) + others
            + '<ReportParameterAttr><Parameters/></ReportParameterAttr>'
            + '<StyleList><Style/><Style/></StyleList></WorkBook>')


def cells_of(text, name="main", block=None):
    grid = cptmodel.DocumentIndex(text).select(name, block)
    return {c.at: c for c in grid.cells}


def formula_at(text, at, name="main", block=None):
    index = cptmodel.DocumentIndex(text)
    grid = index.select(name, block)
    return next(s.expression for s in index.surfaces if s.grid is grid and s.cell
                and s.cell.at == at and s.kind == "formula")


@pytest.mark.parametrize("expr,addresses", [
    ('=C3[B3:-1]+SUM(C3[!0])+&B3', ['C3', 'B3', 'C3', 'B3']),
    ('=COUNT(C3[!0;!0]A{C3>$C3})', ['C3', 'C3', '$C3']),
    ('="A1"+\'B2\'+C3+$param+ds.A1+LOG10(4)+A1_name', ['C3']),
    ("='二 表'!$C3+other!A2", ["'二 表'!$C3", 'other!A2']),
    ('=SUM(A1 : C4)', ['A1 : C4']),
    ('=ds.select(amt,key=$A3)+SUMPRECISE(B3[!0])', ['$A3', 'B3']),
])
def test_reference_tokens(expr, addresses):
    assert [expr[r.start:r.end] for r in cptmodel.formula_refs(expr)] == addresses


def test_index_scopes_and_sparse_references():
    text = book(cell('D1', formula='=A1'), others=sheet(cell('A1', value='x'), name='second'))
    index = cptmodel.DocumentIndex(text)
    assert index.report()['can_apply']
    assert index.references('main', at='A1')['references'][0]['incoming']
    with pytest.raises(ApiError, match='多 sheet'):
        index.select()


def test_generated_skeleton_is_ready_for_structure_edits():
    text, _ = reportops.plan_cell(cptxml.empty_skeleton(), 'C2', formula='=$B2*2')
    updated, _, _ = cpttransform.plan_axis(text, 'column', insert_before='B')
    assert formula_at(updated, 'D2', name='sheet1') == '=$C2*2'


@pytest.mark.parametrize('bad,code', [
    ('<WorkBook>', 'invalid_xml'),
    ('<TableDataMap/>', 'invalid_root'),
    (book(cell('A1', value='a') + cell('A1', value='b')), 'duplicate_cell'),
    (book(cell('A1', value='a', style=9)), 'invalid_style'),
    (book(cell('A1', value='a', left='B1') + cell('B1', value='b', left='A1')), 'parent_cycle'),
])
def test_validation_errors(bad, code):
    with pytest.raises(TemplateValidationError) as exc:
        cptmodel.assert_valid(cptmodel.DocumentIndex(bad))
    assert code in [d['code'] for d in exc.value.details['diagnostics']]


def test_delete_columns_changes_only_real_references_and_settings():
    extra = ('<ReportPageAttr><HC F="1" T="3"/></ReportPageAttr>'
             '<ReportAttrSet><ReportSettings><FrozenColumnRow columnrow="3,1"/></ReportSettings></ReportAttrSet>')
    text = book(cell('H9', value='keep C3') + cell('D2', formula='=C3[B3:-1]+SUM(C3[!0])+"C3"')
                + cell('D4', formula='=SUM(A1:D1)'), extra=extra)
    # 删除 A 以外的空白列不会要求该列存在 <C> 节点。
    result, _, details = cpttransform.plan_axis(text, 'column', delete=['A'])
    assert formula_at(result, 'C2') == '=B3[A3:-1]+SUM(B3[!0])+"C3"'
    assert formula_at(result, 'C4') == '=SUM(A1:C1)'
    assert 'keep C3' in result and "select 'C3' as v" in result
    assert '<!-- untouched A1 -->' in result and result.startswith('\ufeff')
    assert '<HC F="0" T="2"/>' in result
    assert 'columnrow="2,1"' in result
    assert '5616000,8424000,11232000' in result
    assert details['reference_updates']


def test_delete_referenced_target_is_a_conflict_even_when_it_is_blank():
    with pytest.raises(TemplateValidationError) as exc:
        cpttransform.plan_axis(book(cell('C1', formula='=B1')), 'column', delete=['B'])
    assert exc.value.details['diagnostics'][0]['code'] == 'deleted_reference'


def test_dependencies_inside_removed_content_do_not_block():
    result, _, _ = cpttransform.plan_axis(book(cell('B1', formula='=B1')), 'column', delete=['B'])
    assert cells_of(result) == {}


def test_normalize_multiple_deletions_against_original_coordinates():
    text = book(''.join(cell(f'A{r}', value=str(r)) for r in range(1, 9)))
    result, _, _ = cpttransform.plan_axis(text, 'row', delete=['2:3', '3:4', '7'])
    index = cptmodel.DocumentIndex(result)
    assert [index.value(index.child(c.element, 'O')).strip() for c in index.grids[0].cells] == ['1', '5', '6', '8']
    assert [c.at for c in index.grids[0].cells] == ['A1', 'A2', 'A3', 'A4']


def test_partial_reference_range_shrinks_and_entire_deleted_range_blocks():
    text = book(cell('D5', formula='=SUM(A1:A4)'))
    result, _, _ = cpttransform.plan_axis(text, 'row', delete=['1:2'])
    assert formula_at(result, 'D3') == '=SUM(A1:A2)'
    with pytest.raises(TemplateValidationError):
        cpttransform.plan_axis(text, 'row', delete=['1:4'])


def test_insertion_expands_merge_inside_but_shifts_at_boundary():
    text = book(cell('B2', value='title', cs=3) + cell('F5', formula='=$D2'))
    result, _, _ = cpttransform.plan_axis(text, 'column', insert_before='C', count=2)
    assert cells_of(result)['B2'].cs == 5
    assert formula_at(result, 'H5') == '=$F2'
    shifted, _, _ = cpttransform.plan_axis(text, 'column', insert_before='B')
    assert cells_of(shifted)['C2'].cs == 3


def test_partial_deletion_of_nonempty_merge_anchor_blocks():
    with pytest.raises(TemplateValidationError) as exc:
        cpttransform.plan_axis(book(cell('A1', value='title', cs=3)), 'column', delete=['A'])
    assert exc.value.details['diagnostics'][0]['code'] == 'deleted_merge_anchor'
    result, _, _ = cpttransform.plan_axis(book(cell('A1', value='', cs=3)), 'column', delete=['A'])
    assert cells_of(result)['A1'].cs == 2


def test_cross_sheet_update_and_sheet_rename_delete():
    text = book(cell('C1', value='data'), others=sheet(cell('A1', formula='=main!C1') + cell('A2', formula='=C1'), name='second'))
    result, _, _ = cpttransform.plan_axis(text, 'column', sheet='main', delete=['B'])
    assert formula_at(result, 'A1', 'second') == '=main!B1'
    assert formula_at(result, 'A2', 'second') == '=C1'
    renamed, _, _ = cpttransform.plan_sheet(result, 'main', new_name='new name')
    assert formula_at(renamed, 'A1', 'second') == "='new name'!B1"
    with pytest.raises(TemplateValidationError):
        cpttransform.plan_sheet(text, 'main', remove=True)
    cpttransform.plan_sheet(text, 'second', remove=True)


def test_all_formula_carriers_and_parent_are_shifted():
    inner = ('<HighlightList><Highlight><Condition class="com.fr.data.condition.FormulaCondition"><Formula><![CDATA[=$C2>0]]></Formula></Condition>'
             '</Highlight></HighlightList><NameJavaScriptGroup><Parameters><Parameter>'
             '<O t="Formula" class="Formula"><Attributes><![CDATA[=$C2]]></Attributes></O>'
             '</Parameter></Parameters></NameJavaScriptGroup>')
    target = cell('D2', formula='=C2', left='C2').replace('</C>', inner + '</C>')
    result, _, _ = cpttransform.plan_axis(book(cell('C2', value='p') + target), 'column', delete=['B'])
    assert 'left="B2"' in result
    assert '<![CDATA[=$B2>0]]>' in result
    assert '<![CDATA[=$B2]]>' in result
    assert formula_at(result, 'C2') == '=B2'


def test_implicit_parent_removed_is_detected():
    text = book(cell('A2', value='p', expand='v') + cell('B2', value='detail'))
    with pytest.raises(TemplateValidationError) as exc:
        cpttransform.plan_axis(text, 'column', delete=['A'])
    assert exc.value.details['diagnostics'][0]['kind'] == 'implicit-parent'


def test_implicit_parent_directions_spans_and_explicit_barrier():
    text = book(cell('A1', value='v', expand='v', rs=2)
                + cell('C2', value='detail')
                + cell('F1', value='h', expand='h', cs=2)
                + cell('G4', value='under')
                + cell('A5', value='below vertical'))
    index = cptmodel.DocumentIndex(text)
    implicit = {(s.cell.at, s.attr): s.expression for s in index.surfaces if s.implicit}
    assert implicit['C2', 'left'] == 'A1'
    assert implicit['G4', 'up'] == 'F1'
    assert ('A5', 'up') not in implicit


def test_structured_coordinates_in_conditions_widgets_and_writeback():
    payload = ('<Condition><Compare><ColumnRow column="2" row="3"/></Compare></Condition>'
               '<Widget class="com.fr.form.ui.DeleteRowButton"><FixCell col="2" row="3"/></Widget>')
    result, _, details = cpttransform.plan_axis(book(cell('D5', value='x').replace('</C>', payload+'</C>')),
                                               'column', delete=['A'])
    assert '<ColumnRow column="1" row="3"/>' in result
    assert '<FixCell col="1" row="3"/>' in result
    assert len(details['reference_updates']) == 2


def test_unverified_qualifier_is_reported_instead_of_rewritten():
    with pytest.raises(TemplateValidationError) as exc:
        cpttransform.plan_axis(book(cell('C3', formula='=main~B1')), 'column', delete=['A'])
    assert exc.value.details['diagnostics'][0]['code'] == 'unknown_qualified_reference'


def test_multiple_removed_dependencies_are_reported_together():
    with pytest.raises(TemplateValidationError) as exc:
        cpttransform.plan_axis(book(cell('C1', formula='=B1') + cell('D2', formula='=B2')),
                               'column', delete=['B'])
    assert len(exc.value.details['diagnostics']) == 2


@pytest.mark.parametrize('payload', [
    '<JavaScript class="com.fr.js.JavaScriptImpl"><Content>readCell("A1")</Content></JavaScript>',
    '<FloatElementList><Float/></FloatElementList>',
    '<O t="XMLable" class="plugin.CustomThing"/>',
])
def test_unknown_structures_are_reported_and_block_shift(payload):
    text = book(cell('C3', value='x'), extra=payload)
    index = cptmodel.DocumentIndex(text)
    assert index.report()['unsupported'] and not index.report()['coverage_complete']
    with pytest.raises(TemplateValidationError):
        cpttransform.plan_axis(text, 'column', delete=['B'])


def test_dynamic_formula_blocks_but_string_literal_does_not():
    with pytest.raises(TemplateValidationError):
        cpttransform.plan_axis(book(cell('C3', formula='=EVAL("A1")')), 'row', insert_before='1')
    cpttransform.plan_axis(book(cell('C3', formula='="EVAL(A1)"')), 'row', insert_before='1')


def test_copy_references_and_preserve_source():
    text = book(cell('A1', value='value') + cell('B1', formula='=A1+other!A1'), others=sheet(name='other'))
    result, _, _ = cpttransform.plan_range(text, 'A1:B1', sheet='main', copy_to='D2')
    assert formula_at(result, 'B1') == '=A1+other!A1'
    assert formula_at(result, 'E2') == '=D2+other!D2'


def test_excel_notation_and_value_position_copy_are_not_guessed():
    for expression in ('=$B$2', '=B$2', '=SUM($A$1:C3)'):
        with pytest.raises(TemplateValidationError) as exc:
            cpttransform.plan_axis(book(cell('D4', formula=expression)), 'column', delete=['A'])
        assert exc.value.details['diagnostics'][0]['code'] == 'excel_style_address'
    with pytest.raises(TemplateValidationError) as exc:
        cpttransform.plan_range(book(cell('B1', formula='=$A1')), 'A1:B1', copy_to='D2')
    assert exc.value.details['diagnostics'][0]['code'] == 'copy_value_position'


def test_move_updates_incoming_and_handles_overlap_snapshot():
    text = book(cell('A1', value='x') + cell('B1', formula='=A1') + cell('D4', formula='=B1'))
    result, _, _ = cpttransform.plan_range(text, 'A1:B1', move_to='B1')
    assert set(cells_of(result)) == {'B1', 'C1', 'D4'}
    assert formula_at(result, 'C1') == '=B1'
    assert formula_at(result, 'D4') == '=C1'


def test_range_conflicts_and_noop():
    text = book(cell('A1', value='x') + cell('D1', value='occupied'))
    with pytest.raises(TemplateValidationError):
        cpttransform.plan_range(text, 'A1:B1', copy_to='D1')
    assert cpttransform.plan_range(text, 'A1:B1', move_to='A1')[0] == text
    with pytest.raises(TemplateValidationError):
        cpttransform.plan_range(book(cell('A1', value='x', cs=2)), 'B1', clear=True)


def test_merge_unmerge_clear_and_sparse_styles():
    text = book(cell('A1', value='title', style=0) + cell('B1', value=''))
    merged, _, _ = cpttransform.plan_range(text, 'A1:B1', merge=True)
    assert cells_of(merged)['A1'].cs == 2
    unmerged, _, _ = cpttransform.plan_range(merged, 'A1:B1', unmerge=True)
    assert cells_of(unmerged)['A1'].cs == 1
    cleared, _, _ = cpttransform.plan_range(merged, 'A1:B1', clear=True)
    assert cells_of(cleared)['A1'].cs == 2
    assert cells_of(cleared)['A1'].element.attrs['s'] == '0'
    styled, _, _ = cpttransform.plan_range(book(), 'A1:B2', style=1)
    assert len(cells_of(styled)) == 4
    assert all(c.element.attrs['s'] == '1' for c in cells_of(styled).values())


def test_poly_blocks_are_independent_and_legacy_grid_commands_accept_scope():
    blocks = '<Block><PECBAttr blockName="left"/>' + sheet(cell('B1', value='left')).split('>', 1)[1].rsplit('</Report>', 1)[0] + '</Block>'
    blocks += '<Block><PECBAttr blockName="right"/><CellElementList>' + cell('B1', value='right') + '</CellElementList></Block>'
    text = book(main='<Report class="com.fr.report.worksheet.PolyWorkSheet" name="main">' + blocks + '</Report>')
    with pytest.raises(ApiError, match='--block'):
        cpttransform.plan_axis(text, 'column', delete=['A'])
    result, _, _ = cpttransform.plan_axis(text, 'column', block=1, delete=['A'])
    assert set(cells_of(result, block=1)) == {'A1'}
    assert set(cells_of(result, block=2)) == {'B1'}
    changed, _ = reportops.plan_cell(text, 'B1', sheet=cptmodel.GridScope('main', 2), value='new')
    assert 'new' in changed and 'left' in changed


def test_row_height_column_width_hide_and_invalid_input():
    text, _, _ = cpttransform.plan_axis(book(), 'row', at='2:3', size=20)
    assert '442000,885500,885500,1768000' in text
    hidden, _, _ = cpttransform.plan_axis(text, 'column', at='B:C', hide=True)
    assert '2808000,0,0,11232000' in hidden
    for kwargs in ({'delete': ['4:2']}, {'insert_before': '0'}, {'size': float('nan'), 'at': '1'}):
        with pytest.raises(ApiError):
            cpttransform.plan_axis(book(), 'row', **kwargs)


def test_randomized_nonadjacent_deletes_preserve_surviving_values():
    rng = random.Random(773)
    for _ in range(15):
        removed = set(rng.sample(range(1, 20), 5))
        source = book(''.join(cell(f'A{r}', value=str(r)) for r in range(1, 21)))
        text, _, _ = cpttransform.plan_axis(source, 'row', delete=[str(r) for r in removed])
        index = cptmodel.DocumentIndex(text)
        assert [int(index.value(index.child(c.element, 'O')).strip()) for c in index.grids[0].cells] == [
            r for r in range(1, 21) if r not in removed]


def test_local_cli_no_config_network_and_no_dry_run_writes(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('offline command touched config/network')
    monkeypatch.setattr(commands, 'load_config', forbidden)
    monkeypatch.setattr(commands, 'get_client', forbidden)
    monkeypatch.setattr(reportops, 'RemoteDesignSession', forbidden)
    source, output = tmp_path / 'in.cpt', tmp_path / 'out.cpt'
    source.write_text(book(cell('C3', formula='=C1')), encoding='utf-8')
    runner = CliRunner()
    for args in (['validate'], ['refs'], ['column', '--delete', 'B']):
        res = runner.invoke(commands.report_group, [args[0], str(source), '--local', *args[1:]])
        assert res.exit_code == 0, res.output
    res = runner.invoke(commands.report_group, ['column', str(source), '--local', '--delete', 'B', '-o', str(output)])
    assert res.exit_code == 0 and not output.exists()
    res = runner.invoke(commands.report_group, ['column', str(source), '--local', '--delete', 'B', '--apply', '-o', str(output)])
    assert res.exit_code == 0, res.output
    assert json.loads(res.output)['upload']['verified']
    assert formula_at(output.read_text(encoding='utf-8'), 'B3') == '=B1'
    for dest in (source, output):
        res = runner.invoke(commands.report_group, ['column', str(source), '--local', '--delete', 'B', '--apply', '-o', str(dest)])
        assert res.exit_code != 0


@pytest.mark.parametrize('command,options', [
    ('cell', ['--at', 'A1', '--set-value', 'hello']),
    ('dataset', ['--add', 'new', '--conn', 'demo_conn', '--sql', 'select 1']),
    ('param', ['--add', 'date=20260101']),
    ('style', ['--add', '--bold']),
    ('sheet', ['--add', 'second']),
    ('table', ['--dataset', 'ds', '--at', 'A2', '--columns', 'v']),
    ('highlight', ['--at', 'A1', '--rule', 'v>0:bg=#FF0000']),
    ('link', ['--at', 'A1', '--to', 'https://reports.example.com', '--type', 'web']),
    ('edit', ['--dataset', 'ds', '--sql', 'select 2']),
])
def test_existing_edit_commands_support_local(tmp_path, monkeypatch, command, options):
    source = tmp_path / 'in.cpt'
    source.write_text(book(cell('A1', value='x')), encoding='utf-8')
    monkeypatch.setattr(commands, 'load_config', lambda *a: pytest.fail('loaded instance'))
    result = CliRunner().invoke(commands.report_group, [command, str(source), '--local', *options])
    assert result.exit_code == 0, result.output


def test_local_conflict_has_nonzero_code_no_output(tmp_path):
    source, output = tmp_path / 'in.cpt', tmp_path / 'out.cpt'
    source.write_text(book(cell('C1', formula='=B1')), encoding='utf-8')
    result = CliRunner().invoke(commands.report_group, ['column', str(source), '--local', '--delete', 'B', '--apply', '-o', str(output)])
    assert result.exit_code == 1
    assert 'deleted_reference' in result.output and not output.exists()


def test_local_relative_parent_path_is_not_a_remote_path_traversal(tmp_path, monkeypatch):
    source = tmp_path / 'source.cpt'
    source.write_text(book(cell('A1', value='x')))
    child = tmp_path / 'child'
    child.mkdir()
    monkeypatch.chdir(child)
    result = CliRunner().invoke(commands.report_group, ['edit', '../source.cpt', '--local', '--list'])
    assert result.exit_code == 0, result.output


def test_unknown_coordinate_payload_does_not_claim_coverage():
    for payload in ('<NewPlugin ref="C3"/>', '<CellAddress><![CDATA[C3]]></CellAddress>'):
        with pytest.raises(TemplateValidationError):
            cpttransform.plan_axis(book(cell('C3', value='x'), extra=payload), 'column', delete=['A'])


def test_dataset_fields_that_look_like_cells_are_preserved():
    text = book(cell('D3', formula='=SUM(ds.select(A1,Q1=$C3))'))
    result, _, _ = cpttransform.plan_axis(text, 'column', insert_before='B')
    assert formula_at(result, 'E3') == '=SUM(ds.select(A1,Q1=$D3))'
    with pytest.raises(TemplateValidationError) as exc:
        cpttransform.plan_axis(book(cell('D3', formula='=SUM(ds.select(amt,key=C3))')),
                               'column', insert_before='B')
    assert exc.value.details['diagnostics'][0]['code'] == 'ambiguous_dataset_reference'


def test_declared_parameter_with_cell_like_name_is_not_rewritten():
    text = book(cell('C3', formula='=$A1')).replace('<Parameters/>',
        '<Parameters><Parameter><Attributes name="A1"/><O>10</O></Parameter></Parameters>')
    with pytest.raises(TemplateValidationError) as exc:
        cpttransform.plan_axis(text, 'column', insert_before='A')
    assert exc.value.details['diagnostics'][0]['code'] == 'ambiguous_parameter_reference'
