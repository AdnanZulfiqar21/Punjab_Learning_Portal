"""OCR one scanned textbook PDF into a page-marked text layer.

Usage:  python ocr_pdf.py "<pdf path>" "<output .txt>"
Requires: pip install pymupdf winocr pillow   (Windows 10/11 built-in OCR engine, English language pack)
Run one process per PDF in parallel; ~1 s/page/process at 200 DPI.
"""
import pymupdf, os, sys, time, json, warnings
warnings.filterwarnings("ignore")
import winocr
from PIL import Image
f=sys.argv[1]; out=sys.argv[2]
d=pymupdf.open(f); low=[]; t0=time.time()
with open(out,"w",encoding="utf-8") as o:
    for i,p in enumerate(d):
        pix=p.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY)
        img=Image.frombytes("L",(pix.width,pix.height),pix.samples).convert("RGB")
        try:
            r=winocr.recognize_pil_sync(img,"en")
            lines=[l["text"] for l in r.get("lines",[])] if isinstance(r,dict) else []
        except Exception as e:
            lines=[f"[OCR ERROR {e}]"]
        txt="\n".join(lines)
        if len(txt)<80: low.append(i+1)
        o.write(f"\n=====PAGE {i+1}=====\n{txt}\n"); o.flush()
print(json.dumps({"file":f,"pages":d.page_count,"low_text_pages":low,"secs":round(time.time()-t0)}))
