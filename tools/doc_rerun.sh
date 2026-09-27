#!/usr/bin/env bash
# 照 references/cpt-patterns2.md 的配方**逐条重跑**（独立验证/回归用）。
#
# 为什么要有这个脚本：文档里写着"逐条真跑过"，但只在临时目录跑等于没跑 ——
# 别人 find 不到、无法复核。本脚本把它落进仓库，任何人可一键重放：
#
#   export FRCLI_WRITE_SCOPE="demo_group/demo_user/skill测试"   # ← 写范围（fail-closed，不设会拒绝）
#   export FRCLI_TIMEOUT=300                                     # 复杂版面默认 30s 会超时
#   bash tools/doc_rerun.sh                                      # 成功打印 DOC-RERUN-OK
#
# ⚠ 它会**在服务器上新建/覆盖** `patterns/verify/` 下的 4 张验证件（这是有意的：留下可复现证据）。
#    只在被授权的测试目录里跑；`set -e` 保证任何一步异常/空操作中途退出都会失败（幂等性回归）。
set -e
cd "$(dirname "$0")/.."                  # 仓库根目录
if [ -z "$FRCLI_WRITE_SCOPE" ]; then
  echo "❌ 先 export FRCLI_WRITE_SCOPE=<被授权的测试目录>（写操作 fail-closed）" >&2
  exit 2
fi
frcli(){ PYTHONPATH=src <venv>/bin/python -m frcli "$@"; }
B="demo_group/demo_user/skill测试/patterns/verify"
R="$B/v_chart.cpt"
# ---- §W1 图表（照文档逐条）----
frcli report new "$R" --apply --force >/dev/null
frcli report dataset "$R" --add ds1 --conn demo_conn \
  --sql "select '东区' cat,'A' series,100 val union all select '东区','B',200 union all select '西区','A',300 union all select '西区','B',400" --apply >/dev/null
frcli report chart "$R" --at A1 --dataset ds1 --type column --category cat --series series --value val --fn sum --title "各区域 A/B 销量" --show-title --apply >/dev/null
frcli report chart "$R" --list >/dev/null
frcli export image "$R" -o /tmp/cptlab/verify_chart.png >/dev/null
# ---- §W4 层次坐标 ----
R2="$B/v_coord.cpt"
frcli report new "$R2" --apply --force >/dev/null
frcli report dataset "$R2" --add ds1 --conn demo_conn \
  --sql "select '东区' dist,'2024' yr,100 amt union all select '东区','2025',150 union all select '西区','2024',200 union all select '西区','2025',100" --apply >/dev/null
frcli report table "$R2" --dataset ds1 --at A2 --columns dist,yr,amt --header --labels "地区,年份,金额" --apply >/dev/null
frcli report cell "$R2" --at A3 --set-ds-mode group --expand v --apply >/dev/null
frcli report cell "$R2" --at D3 --set-formula '=C3/C3[B3:-1]-1' --num-format '#0.0%' --apply >/dev/null
frcli report cell "$R2" --at E3 --set-formula '=C3/C3[A3:-1]-1' --num-format '#0.0%' --apply >/dev/null
frcli report cell "$R2" --at H3 --set-formula '=C3/SUM(C3[!0])' --num-format '#0.0%' --apply >/dev/null
frcli export excel "$R2" -o /tmp/cptlab/verify_w4.xlsx >/dev/null
# ---- §W2 控件 + §W3 链接 ----
R3="$B/v_widget_link.cpt"
frcli report new "$R3" --apply --force >/dev/null
frcli report dataset "$R3" --add ds1 --conn demo_conn --sql "select * from (select '华东' area,100 amt union all select '华南',200) t where area = '\${area}'" --param area=华东 --apply >/dev/null
frcli report table "$R3" --dataset ds1 --at A2 --columns area,amt --header --labels "地区,金额" --apply >/dev/null
frcli report widget "$R3" --param area --type combo --options 华东,华南 --default 华东 --apply >/dev/null
frcli report widget "$R3" --list >/dev/null
frcli report link "$R3" --at A3 --to "$B/v_coord.cpt" --param center='=$A3' --param flag=1 --apply >/dev/null
frcli report link "$R3" --list >/dev/null
frcli export excel "$R3" -o /tmp/cptlab/verify_w2.xlsx --params '{"area":"华南"}' >/dev/null
# ---- §W5 分页/页脚 ----
R4="$B/v_page.cpt"
frcli report new "$R4" --apply --force >/dev/null
frcli report dataset "$R4" --add ds1 --conn demo_conn --sql "select 'C1' c,1 v union all select 'C2',2" --apply >/dev/null
frcli report table "$R4" --dataset ds1 --at A2 --columns c,v --header --labels "K,V" --apply >/dev/null
frcli report page "$R4" --repeat-header-rows 1:1 --footer-text '"第 " + $$page_number + " 页"' --footer-formula --footer-height 20 --apply >/dev/null
frcli report page "$R4" --list >/dev/null
frcli export pdf "$R4" -o /tmp/cptlab/verify_w5.pdf >/dev/null
# ---- 幂等：同一条命令再跑一次不应 exit 1 ----
frcli report page "$R4" --repeat-header-rows 1:1 >/dev/null
frcli report widget "$R3" --param area --type combo --options 华东,华南 --default 华东 >/dev/null
echo "DOC-RERUN-OK"
