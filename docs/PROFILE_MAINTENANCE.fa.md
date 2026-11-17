# نگهداری پروفایل

README فقط کارت ترمینال را نمایش می‌دهد. دو فایل SVG روشن و تیره با `scripts/render_neofetch.py` از `data/profile.json` ساخته می‌شوند. تعداد مخازن عمومی، دنبال‌کنندگان و ستاره‌ها خودکار است؛ ستاره‌ها از مخازن عمومی غیرفورک به جز مخزن پروفایل محاسبه می‌شوند. سایر متن‌ها و لوگوی ASCII در اسکریپت قابل ویرایش‌اند.

GitHub Actions روزانه ساعت 04:17 UTC داده‌ها را دریافت و کارت‌ها را بازسازی می‌کند. اجرای دستی از Actions → Update profile → Run workflow ممکن است. در صورت خطای دریافت، snapshot قبلی حفظ می‌شود.

برای بازسازی و بررسی محلی:

```bash
python3 scripts/update_profile.py --offline
python3 scripts/render_neofetch.py
python3 -m unittest discover -s tests -v
python3 scripts/update_profile.py --offline --check
python3 scripts/render_neofetch.py --check
```
