"""结构编辑的写入边界、并发检测和本地新文件契约。"""

import hashlib

import pytest
from click.testing import CliRunner

from frcli import cptxml, remotedesign, reportops
from frcli.commands.report import report_group
from frcli.exceptions import ApiError


def test_programmatic_apply_checks_scope_before_read(monkeypatch):
    monkeypatch.delenv('FRCLI_WRITE_SCOPE', raising=False)
    monkeypatch.delenv('FRCLI_ALLOW_ANY_PATH', raising=False)
    monkeypatch.setattr(reportops, 'read_template', lambda *a: pytest.fail('read before scope'))
    with pytest.raises(ApiError, match='未指定范围'):
        reportops.edit_cell(None, 'demo_group/other/x.cpt', apply=True, at='A1', value='x')


@pytest.mark.parametrize('exists,match', [(True, False), (False, False), (True, True)])
def test_upload_compares_snapshot_under_lock_and_releases_it(tmp_path, monkeypatch, exists, match):
    original = cptxml.empty_skeleton().encode()
    replacement = original.replace(b'sheet1', b'sheet2')
    source = tmp_path / 'new.cpt'
    source.write_bytes(replacement)
    events = []

    class Session:
        data = original

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def check(self):
            events.append('check')

        def exist(self, path):
            return exists

        def lock(self, path):
            events.append('lock')
            return self.data

        def unlock(self, path):
            events.append('unlock')

        def write(self, path, data):
            events.append('write')
            self.data = data

        def read(self, path):
            events.append('read')
            return self.data

    monkeypatch.setenv('FRCLI_WRITE_SCOPE', 'demo_group/demo_user')
    monkeypatch.setattr(remotedesign, 'RemoteDesignSession', lambda *a: Session())
    monkeypatch.setattr(remotedesign, '_save_backup', lambda *a: events.append('backup') or 'backup.cpt')
    expected = hashlib.sha256(original if match else b'old snapshot').hexdigest()
    if not match:
        with pytest.raises(ApiError, match='已变化'):
            remotedesign.upload_template(None, str(source), 'demo_group/demo_user/x.cpt',
                                         force=True, expected_sha256=expected)
        assert 'write' not in events and 'backup' not in events
        assert ('unlock' in events) is exists
    else:
        result = remotedesign.upload_template(None, str(source), 'demo_group/demo_user/x.cpt',
                                              force=True, expected_sha256=expected)
        assert result['verified']
        assert events.index('lock') < events.index('backup') < events.index('write') < events.index('unlock')


def test_local_new_and_source_snapshot(tmp_path, monkeypatch):
    output = tmp_path / 'new.cpt'
    result = CliRunner().invoke(report_group, ['new', 'new.cpt', '--local', '--apply', '-o', str(output)])
    assert result.exit_code == 0, result.output
    old = output.read_text()
    changed, changes = reportops.plan_cell(old, 'A1', value='hello')
    target = reportops.LocalTemplate(str(output), str(tmp_path / 'result.cpt'))
    output.write_text(old + '\n')
    with pytest.raises(ApiError, match='已变化'):
        reportops.commit(target, str(output), old, changed, 'cell', changes, apply=True)
    assert not (tmp_path / 'result.cpt').exists()


def test_symlink_output_and_dry_run_parent_do_not_write(tmp_path):
    original = cptxml.empty_skeleton()
    source = tmp_path / 'source.cpt'
    source.write_text(original)
    new, changes = reportops.plan_cell(original, 'A1', value='x')
    output = tmp_path / 'missing' / 'out.cpt'
    local = reportops.LocalTemplate(str(source), str(output))
    reportops.commit(local, str(source), original, new, 'cell', changes)
    assert not output.parent.exists()
    link = tmp_path / 'out.cpt'
    link.symlink_to(output)
    local.output = str(link)
    with pytest.raises(ApiError, match='已存在'):
        reportops.commit(local, str(source), original, new, 'cell', changes, apply=True)
    assert not output.exists()
