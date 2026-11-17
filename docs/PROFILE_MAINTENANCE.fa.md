# نگهداری پروفایل

README فقط کارت ترمینال را نمایش می‌دهد. دو فایل SVG روشن و تیره از `data/profile.json` و `data/pinned.json` ساخته می‌شوند. معرفی و موقعیت از فیلدهای پروفایل، و دو پروژهٔ پین‌شدهٔ اول از GitHub GraphQL می‌آیند. زبان‌ها پرتکرارترین زبان اصلی مخازن عمومی غیرفورک‌اند و معیار مهارت نیستند. ستاره‌ها از مخازن عمومی غیرفورک به جز مخزن پروفایل محاسبه می‌شوند. لوگو و ظاهر کارت ثابت‌اند.

برای حفظ شبکهٔ ثابت ترمینال در دستگاه‌های مختلف، مسیرهای حروف فونت DejaVu Sans Mono در `assets/terminal-glyphs.json.gz` ذخیره و هنگام ساخت SVG استفاده می‌شوند. مجوز فونت در `assets/DEJAVU-LICENSE.txt` است. کاراکترهایی که در فونت موجود نیستند به شکل علامت سؤال نمایش داده می‌شوند.

GitHub Actions روزانه ساعت 04:17 UTC داده‌ها را دریافت و کارت‌ها را بازسازی می‌کند. اجرای دستی از Actions → Update profile → Run workflow ممکن است. در صورت خطای دریافت، snapshot قبلی حفظ می‌شود.

دریافت پین‌ها به `GITHUB_TOKEN` نیاز دارد؛ workflow از توکن موقت خود GitHub استفاده می‌کند. پس از تغییر پین‌ها، حداکثر با اجرای روزانهٔ بعدی کارت به‌روز می‌شود. فهرست منتخب قدیمی در `profile.json` در کارت استفاده نمی‌شود.

برای بازسازی و بررسی محلی:

```bash
python3 scripts/update_profile.py --offline
python3 scripts/render_neofetch.py
python3 -m unittest discover -s tests -v
python3 scripts/update_profile.py --offline --check
python3 scripts/render_neofetch.py --check
```
