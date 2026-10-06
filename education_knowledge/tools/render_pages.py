# usage: python render.py "<pdf path>" <first_pdf_page> <last_pdf_page> <out.png> [dpi]
import pymupdf, sys
from PIL import Image
f,a,b,out=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4]; dpi=int(sys.argv[5]) if len(sys.argv)>5 else 70
d=pymupdf.open(f); ims=[]
for p in range(a,b+1):
    pix=d[p-1].get_pixmap(dpi=dpi); ims.append(Image.frombytes("RGB",(pix.width,pix.height),pix.samples))
w=max(i.width for i in ims); h=max(i.height for i in ims); cols=min(len(ims),4)
s=Image.new("RGB",(w*cols,h*((len(ims)+cols-1)//cols)),"white")
for k,im in enumerate(ims): s.paste(im,((k%cols)*w,(k//cols)*h))
s.save(out); print("saved",out)
