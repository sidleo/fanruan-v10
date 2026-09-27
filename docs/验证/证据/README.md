# 关于证据文件

本目录原先存放验证过程的服务端渲染产物（PNG/PDF）与数据导出（XLSX）。

**已全部移除**，原因：服务端渲染的产物**带个人水印**（姓名 + 工号）且可能含真实经营数据，
本仓库可能公开，不适合留存。

## 需要复查证据时怎么重建

证据本身由**可复现命令**产生，不必依赖存档文件：

```bash
# 图表 / 分页类特性 → 出图看（image 不渲染页眉页脚，分页类必须走 PDF）
frcli export image <模板> -o /tmp/x.png
frcli export pdf   <模板> -o /tmp/x.pdf
python -c "import pypdfium2 as pdfium; p=pdfium.PdfDocument('/tmp/x.pdf'); \
           print(len(p)); p[0].render(scale=1.6).to_pil().save('/tmp/p1.png')"

# 行内类特性 → 逐格读回
frcli export excel <模板> -o /tmp/x.xlsx     # 再用 openpyxl 逐格读
```

各验证报告里保留了当时的**逐格数值**与**复现命令**，结论不依赖这些图片。
