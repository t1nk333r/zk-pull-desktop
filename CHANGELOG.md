# Release notes · سجل التغييرات

Each version's section becomes the description of its GitHub release.

## 0.3.0 (2026-11-12)

Installed from 0.2.0, the app offers this update by itself. From 0.1.0, run the installer once by hand.

**Changed**
- **Pull saves only the period you chose.** The device still sends its whole log (it cannot send part of it), but only punches between From and To are kept.

**New**
- **Cancel** a pull; a device that is off no longer stops the others, and one message sums up the results. The last pull time shows next to the device.
- **Search** the Attendance table by ID, name or department; exports contain what is shown.
- **Export layout** (punch log or daily summary) is chosen next to the Export button.
- **Shortcuts:** F5 pull, Ctrl+E export, Ctrl+F search. The window remembers its size and tab.
- **Backups:** a daily copy of the database (last 7 days kept), **Back up database…** in Settings, and recovery from a damaged database. **Open log** and **About** in Settings.
- Clear messages for an empty period, a From date after the To date, and a file open in Excel.

**Security**
- A device that stops answering, sends huge amounts of data or impossible dates can no longer hang the app or block all later pulls; bad records are left out and counted.
- A device answering with another serial number must be confirmed before anything is saved, and two devices' punches are never mixed.
- Names from devices and files are always shown as plain text, so a crafted name cannot make Windows connect to another computer.
- Large Excel/CSV name files are refused or imported in the background.
- Updates require GitHub's published checksum, stop if the download is larger than published, and installs "for all users" are sent to IT instead of failing.
- Releases are published only from `main`, and a published release is never replaced.

**Fixed**
- Arabic date boxes showed dates reversed (01-11-2026).

<div dir="rtl">

إذا كان الإصدار 0.2.0 مثبّتًا فسيعرض البرنامج هذا التحديث تلقائيًا. ومن الإصدار 0.1.0 شغّل المثبّت يدويًا مرة واحدة.

**التغييرات**
- **السحب يحفظ الفترة التي اخترتها فقط.** ما زال الجهاز يرسل سجله كاملًا (لا يستطيع إرسال جزء منه)، لكن لا يُحفظ إلا ما بين تاريخ البداية وتاريخ النهاية.

**الجديد**
- **إلغاء** السحب؛ والجهاز المطفأ لم يعد يوقف بقية الأجهزة، وتلخّص رسالة واحدة النتائج. ويظهر وقت آخر سحب بجانب الجهاز.
- **البحث** في جدول الحضور برقم الموظف أو الاسم أو القسم، والتصدير يحتوي ما يظهر في الجدول.
- **شكل التصدير** (سجل البصمات أو ملخص يومي) يُختار بجانب زر التصدير.
- **اختصارات لوحة المفاتيح:** F5 للسحب، Ctrl+E للتصدير، Ctrl+F للبحث. وتتذكر النافذة حجمها وآخر تبويب.
- **النسخ الاحتياطي:** نسخة يومية من قاعدة البيانات (تُحفظ آخر 7 أيام)، وزر **نسخ احتياطي لقاعدة البيانات…** في الإعدادات، والاستعادة إذا تلفت قاعدة البيانات. وزرا **فتح السجل** و**حول البرنامج** في الإعدادات.
- رسائل واضحة عند فترة بلا بصمات، أو تاريخ بداية بعد تاريخ النهاية، أو ملف مفتوح في Excel.

**الأمان**
- الجهاز الذي يتوقف عن الاستجابة أو يرسل كميات بيانات ضخمة أو تواريخ مستحيلة لم يعد يستطيع تجميد البرنامج أو منع كل عمليات السحب اللاحقة؛ تُستبعد السجلات التالفة ويُذكر عددها.
- إذا ظهر رقم تسلسلي مختلف لجهاز فيجب تأكيده قبل حفظ أي شيء، ولا تُخلط بصمات جهازين أبدًا.
- الأسماء القادمة من الأجهزة والملفات تُعرض دائمًا نصًا عاديًا، فلا يستطيع اسم مصمَّم خصيصًا أن يجعل Windows يتصل بحاسوب آخر.
- ملفات الأسماء الكبيرة جدًا تُرفض، والاستيراد يجري في الخلفية.
- التحديثات تشترط البصمة الرقمية التي ينشرها GitHub، وتتوقف إذا كان الملف أكبر مما نُشر، وعند التثبيت "لجميع المستخدمين" يُطلب من قسم تقنية المعلومات التحديث بدلًا من الفشل.
- الإصدارات تُنشر من الفرع `main` فقط، ولا يُستبدل إصدار منشور أبدًا.

**الإصلاحات**
- كانت مربعات التاريخ في الواجهة العربية تعرض التاريخ معكوسًا (01-11-2026).

</div>

## 0.2.0 (2026-11-12)

**Coming from 0.1.0:** run the 0.2.0 installer over it once. Names and attendance history are kept. From now on, the app updates itself.

**New**
- **Updates itself:** checks for a new version at startup (Settings → Updates), installs it after asking, and restarts. The download is checked against GitHub's published checksum.
- **Opens the exported file** right after export (tick box next to Export).

**Fixed**
- Changing the language, closing the setup wizard or starting a second device action while a device is being read could lose data or skip devices; it now waits.
- Editing a device no longer hides its punches from the device filter; punches stay with a device whose serial number changes.
- One bad character from a device no longer breaks Excel exports; names starting with `-`, `+` or `@` no longer show an apostrophe in Excel; Arabic exports have no hidden characters.
- Arabic CSVs saved by Excel now import; header rows are detected reliably.
- Yes/No/OK buttons in Arabic; corrected Arabic wording (حضور/انصراف).
- Quitting during a pull no longer leaves the app running in the background; only one copy runs at a time.

<div dir="rtl">

**عند الترقية من 0.1.0:** شغّل مثبّت الإصدار 0.2.0 فوقه مرة واحدة، وتبقى الأسماء وسجلات الحضور محفوظة. ومن الآن فصاعدًا يحدّث البرنامج نفسه.

**الجديد**
- **التحديث التلقائي:** يتحقق من وجود إصدار جديد عند التشغيل (الإعدادات ← التحديثات)، ويثبّته بعد السؤال ثم يعيد التشغيل. ويُتحقَّق من الملف المنزَّل مقابل البصمة الرقمية التي ينشرها GitHub.
- **فتح الملف المصدَّر** مباشرة بعد التصدير (مربع اختيار بجانب زر التصدير).

**الإصلاحات**
- تغيير اللغة أو إغلاق معالج الإعداد أو بدء عملية ثانية على الجهاز أثناء قراءته كان قد يُفقد بيانات أو يتخطى أجهزة؛ أصبح البرنامج ينتظر.
- تعديل بيانات جهاز لم يعد يُخفي بصماته من فلتر الأجهزة، وتبقى البصمات مرتبطة بالجهاز إذا تغيّر رقمه التسلسلي.
- حرف تالف واحد من الجهاز لم يعد يمنع التصدير إلى Excel، والأسماء التي تبدأ بـ `-` أو `+` أو `@` لم تعد تظهر بعلامة اقتباس في Excel، وملفات التصدير بالعربية خالية من الأحرف المخفية.
- استيراد ملفات CSV العربية التي يحفظها Excel أصبح يعمل، واكتشاف صف العناوين أصبح موثوقًا.
- أزرار نعم/لا/موافق بالعربية، وتصحيح الصياغة العربية (حضور/انصراف).
- الخروج أثناء السحب لم يعد يترك البرنامج يعمل في الخلفية، ولا يعمل إلا نسخة واحدة في الوقت نفسه.

</div>

## 0.1.0 (2026-11-12)

First release. Pull attendance from ZKTeco devices over the office network and export it to Excel or CSV, in English and Arabic.

- Reads the attendance log from one or more devices (read-only: nothing is ever deleted from a device).
- Quick periods (today, this week, this month, last month) or any dates.
- Export as a punch log or a daily summary (first/last punch, hours), to .xlsx or .csv.
- Employee names from the device, from an Excel/CSV file, or typed in.
- Pulling the same period twice never creates duplicates; exports work offline.

<div dir="rtl">

الإصدار الأول. يسحب سجلات الحضور من أجهزة ZKTeco عبر شبكة المكتب ويصدّرها إلى Excel أو CSV، بالعربية والإنجليزية.

- يقرأ سجل الحضور من جهاز واحد أو أكثر (قراءة فقط: لا يُحذف أي شيء من الجهاز).
- فترات جاهزة (اليوم، هذا الأسبوع، هذا الشهر، الشهر الماضي) أو أي تاريخين.
- التصدير بشكل سجل البصمات أو ملخص يومي (أول وآخر بصمة والساعات) إلى .xlsx أو .csv.
- أسماء الموظفين من الجهاز أو من ملف Excel/CSV أو بإدخالها يدويًا.
- سحب الفترة نفسها مرتين لا يكرر البصمات، والتصدير يعمل دون اتصال بالجهاز.

</div>
