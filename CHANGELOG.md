# Release notes · سجل التغييرات

Each version's section becomes the description of its GitHub release.

## 0.5.0 (2026-11-18)

Installed from 0.2.0 or later, the app offers this update by itself.

**New**
- **Time card export:** a third export layout laid out like the ZKTeco software's Time Card, with the same columns (Name, Date, Timetable, On duty, Off duty, Clock In, Clock Out, Late, Early, Absent, OT Time, Work Time, ATT_Time) and the same rules: late and early after the grace period, overtime from 60 minutes after off duty, absent working days marked, the weekend left out. Checked against a real card exported by the ZKTeco software. The shift, grace periods, overtime threshold and weekend are under **Settings → Time card**; the defaults are those of that card (Daytime 08:00–17:00, 15 minutes grace, Friday off).
- **One employee at a time:** the Attendance tab has an **Employee** list next to the device. Choose someone to see, pull and export only their punches, in any layout; the file name gets their ID (for example `timecard_12_2026-11-01_to_2026-11-30.xlsx`), and a one-person time card's sheet is named after them. The list holds everyone in People and every ID seen in a pull. A pull still saves everyone's punches, as the device always sends its whole log.

<div dir="rtl">

إذا كان الإصدار 0.2.0 أو أحدث مثبّتًا فسيعرض البرنامج هذا التحديث تلقائيًا.

**الجديد**
- **تصدير بطاقة الدوام:** شكل تصدير ثالث مثل بطاقة الدوام في برنامج ZKTeco، بالأعمدة نفسها (الاسم، التاريخ، الدوام، بداية الدوام، نهاية الدوام، الحضور، الانصراف، التأخير، الخروج المبكر، غائب، العمل الإضافي، وقت العمل، وقت الحضور) وبالقواعد نفسها: التأخير والخروج المبكر بعد دقائق السماح، والعمل الإضافي من 60 دقيقة بعد نهاية الدوام، وتمييز أيام العمل التي غاب فيها الموظف، واستبعاد عطلة نهاية الأسبوع. وقد طوبق مع بطاقة حقيقية صدّرها برنامج ZKTeco. والدوام ودقائق السماح وحد العمل الإضافي وعطلة نهاية الأسبوع في **الإعدادات ← بطاقة الدوام**، وقيمها الافتراضية هي قيم تلك البطاقة (Daytime من 08:00 إلى 17:00، و15 دقيقة سماح، والجمعة عطلة).
- **موظف واحد في كل مرة:** في تبويب الحضور قائمة **الموظف** بجانب الجهاز. اختر موظفًا لعرض بصماته وسحبها وتصديرها وحده، بأي شكل، ويُضاف رقمه إلى اسم الملف (مثل `timecard_12_2026-11-01_to_2026-11-30.xlsx`)، وتحمل ورقة بطاقة الموظف الواحد اسمه. تضم القائمة كل من في تبويب الموظفين وكل رقم ظهر في سحب. ويحفظ السحب بصمات الجميع مع ذلك، لأن الجهاز يرسل سجله كاملًا دائمًا.

</div>

## 0.4.1 (2026-11-18)

Installed from 0.2.0 or later, the app offers this update by itself.

**New**
- **Days never pulled are pointed out.** ZK Pull now remembers which days each pull covered. The Attendance tab says when days in the chosen period were never pulled from a device, and Export asks before writing a file where those days would look like absences. Pulls made before this version count as covering everything up to their date.

**Fixed**
- Names files: one bad character in a UTF-8 file no longer turns every Arabic name into garbled text and saves it over the good names; the import now stops and names the line. Files saved as "Unicode Text" import; a comma inside a quoted name no longer picks the wrong separator; IDs such as 0012 in Excel cells formatted 0000 keep their zeros.
- Updates: an update stopped part-way (a locked file, a full disk) no longer leaves an app that cannot start; checking for updates during a download no longer breaks it; a download that finishes during a pull installs after the pull instead of being thrown away; errors now say whether GitHub refused the file or the disk is full; the installer writes update.log in the data folder.
- Old devices with 8-byte records: punches of a deleted user are no longer added to the employee who has the same number; they show as "uid:7".
- CSV: IDs such as 0012 and IDs longer than 15 digits stay as typed in Excel, and names such as #N/A stay text.
- Export: replacing a file is safe if the save fails part-way; a folder Windows does not allow writing to is no longer reported as "the file is open in Excel".
- Back up to a mapped drive or network folder now works.
- A name being typed is no longer lost when an import finishes, and changing the language during a names-file import no longer loses the import.
- Two devices with the same name can be told apart in **Import names from device**.
- A device IP with leading zeros (192.168.100.056) no longer connects to a different device; addresses outside the office network are refused.
- The app no longer ships Qt networking, SVG, software OpenGL and image plugins it does not use; the licences of the remaining components (OpenSSL, bzip2, SQLite and others) are listed. Each build is now started once in CI before it is published.

<div dir="rtl">

إذا كان الإصدار 0.2.0 أو أحدث مثبّتًا فسيعرض البرنامج هذا التحديث تلقائيًا.

**الجديد**
- **التنبيه إلى الأيام التي لم تُسحب.** أصبح ZK Pull يتذكر الأيام التي غطّاها كل سحب. ويبيّن تبويب الحضور الأيام التي لم تُسحب من جهاز ما في الفترة المختارة، ويسأل التصدير قبل كتابة ملف ستظهر فيه تلك الأيام كأنها غياب. والسحوبات التي جرت قبل هذا الإصدار تُعدّ مغطية لكل الأيام حتى تاريخها.

**الإصلاحات**
- ملفات الأسماء: حرف واحد غير صالح في ملف UTF-8 لم يعد يحوّل كل الأسماء العربية إلى رموز مشوّهة ويحفظها مكان الأسماء الصحيحة؛ يتوقف الاستيراد الآن ويذكر رقم السطر. والملفات المحفوظة بصيغة "Unicode Text" تُستورد، والفاصلة داخل اسم بين علامتي اقتباس لم تعد تختار فاصلًا خاطئًا، والأرقام مثل 0012 في خلايا Excel المنسقة 0000 تحتفظ بأصفارها.
- التحديثات: التحديث الذي يتوقف في منتصفه (ملف مقفل أو قرص ممتلئ) لم يعد يترك برنامجًا لا يعمل، والتحقق من التحديثات أثناء التنزيل لم يعد يفسده، والتنزيل الذي ينتهي أثناء السحب يُثبَّت بعد السحب بدلًا من إهماله، والأخطاء تبيّن الآن هل رفض GitHub الملف أم أن القرص ممتلئ، ويكتب المثبّت الملف update.log في مجلد البيانات.
- الأجهزة القديمة ذات السجلات بطول 8 بايت: بصمات المستخدم المحذوف لم تعد تُضاف إلى الموظف الذي يحمل الرقم نفسه، وتظهر باسم "uid:7".
- CSV: الأرقام مثل 0012 والأرقام الأطول من 15 خانة تبقى كما كُتبت في Excel، والأسماء مثل ‎#N/A تبقى نصًا.
- التصدير: استبدال ملف موجود أصبح آمنًا إذا فشل الحفظ في منتصفه، والمجلد الذي لا يسمح Windows بالكتابة فيه لم يعد يُبلَّغ عنه بأن "الملف مفتوح في Excel".
- النسخ الاحتياطي إلى محرك أقراص شبكي أو مجلد على الشبكة يعمل الآن.
- الاسم الذي تكتبه لم يعد يضيع عند انتهاء الاستيراد، وتغيير اللغة أثناء استيراد ملف الأسماء لم يعد يُضيّع الاستيراد.
- يمكن التمييز بين جهازين بالاسم نفسه في **استيراد الأسماء من الجهاز**.
- عنوان IP بأصفار في البداية (192.168.100.056) لم يعد يتصل بجهاز آخر، وتُرفض العناوين من خارج شبكة المكتب.
- لم يعد البرنامج يضم أجزاء Qt للشبكة وSVG وOpenGL البرمجي وإضافات الصور التي لا يستخدمها، وأُدرجت تراخيص المكونات الباقية (OpenSSL وbzip2 وSQLite وغيرها). ويُشغَّل كل إصدار مرة في CI قبل نشره.

</div>

## 0.4.0 (2026-11-16)

Installed from 0.2.0 or 0.3.0, the app offers this update by itself.

**Changed**
- **New licence:** ZK Pull is now Copyright (c) 2026 Abdulrahman Aloqayli under CC BY-NC-ND 4.0. The licences of the bundled components (Qt, PySide6, Python, openpyxl, defusedxml) now ship with the app, under **Settings → Third-party licences**.
- **Own device client:** ZK Pull now talks to the devices with its own code instead of the pyzk library. It sends only read commands, and a test fails if any other command is sent. It gave identical results on the office device (12,880 punches, 27 users).
- The installer is smaller: only the parts of Qt the app uses are included.

**Fixed**
- Deleting or editing a device while it was being pulled could block that device for good or give its history to the next device added; both now wait for the pull.
- A serial number read by **Test connection** at a mistyped address no longer blocks the real device, and changing the IP or port after a Test no longer saves the old serial.
- **Cancel** now works while a device that does not answer is still connecting.
- Backups: a backup cut short (disk full, power cut) no longer takes the place of a good one; recovery offers the newest backup that passes a check; a database that is only locked by another program is no longer treated as damaged; the daily backup also runs when the app stays open for days.
- A pull whose From date is after the To date is refused instead of reading the device for nothing; Export just after midnight uses the new day.
- A failed save (disk full) no longer leaves a multi-device pull stuck on Cancel.
- Device and update errors are shown in Arabic too, with the right cause (a timeout is no longer "unusable data").
- Names files: IDs with letters (E001) no longer lose the first employee; files using semicolons and IDs typed in Arabic digits (١٢) now import; a file with no names is reported instead of "0 added".
- Excel: names such as #N/A stay text, and the daily sheet name is no longer cut off.
- Searching with no match now says so; a new person stays visible while a search is active; Arabic dates in Settings and the pull report read correctly.
- Updates: installs "for me only" in any folder now update themselves, never ask for admin rights, and the app no longer starts after an IT silent install.

<div dir="rtl">

إذا كان الإصدار 0.2.0 أو 0.3.0 مثبّتًا فسيعرض البرنامج هذا التحديث تلقائيًا.

**التغييرات**
- **ترخيص جديد:** حقوق النشر © 2026 Abdulrahman Aloqayli بترخيص CC BY-NC-ND 4.0. وأصبحت تراخيص المكونات المضمّنة (Qt وPySide6 وPython وopenpyxl وdefusedxml) مرفقة بالبرنامج، في **الإعدادات ← تراخيص المكونات الأخرى**.
- **برنامج اتصال خاص بالأجهزة:** أصبح ZK Pull يتصل بالأجهزة بشيفرته الخاصة بدلًا من مكتبة pyzk، ولا يرسل إلا أوامر القراءة، ويفشل اختبار آلي إذا أُرسل أي أمر آخر. وأعطى نتائج مطابقة على جهاز المكتب (12,880 بصمة و27 مستخدمًا).
- المثبّت أصغر حجمًا: لا يضم إلا أجزاء Qt التي يستخدمها البرنامج.

**الإصلاحات**
- حذف جهاز أو تعديله أثناء السحب منه كان قد يمنع ذلك الجهاز نهائيًا أو يعطي سجله لأول جهاز يُضاف بعده؛ أصبح الاثنان ينتظران انتهاء السحب.
- الرقم التسلسلي الذي يقرؤه **اختبار الاتصال** من عنوان خاطئ لم يعد يمنع الجهاز الصحيح، وتغيير عنوان IP أو المنفذ بعد الاختبار لم يعد يحفظ الرقم القديم.
- زر **إلغاء** يعمل الآن أثناء محاولة الاتصال بجهاز لا يستجيب.
- النسخ الاحتياطي: النسخة غير المكتملة (امتلاء القرص أو انقطاع الكهرباء) لم تعد تحل محل نسخة سليمة، والاستعادة تعرض أحدث نسخة تجتاز الفحص، وقاعدة البيانات المقفلة من برنامج آخر لم تعد تُعامل كتالفة، والنسخة اليومية تُؤخذ أيضًا عندما يبقى البرنامج مفتوحًا لأيام.
- السحب الذي يكون فيه تاريخ البداية بعد تاريخ النهاية يُرفض بدلًا من قراءة الجهاز دون فائدة، والتصدير بعد منتصف الليل مباشرة يستخدم اليوم الجديد.
- فشل الحفظ (امتلاء القرص) لم يعد يترك السحب من عدة أجهزة عالقًا على زر الإلغاء.
- أخطاء الأجهزة والتحديث تظهر بالعربية أيضًا وبسببها الصحيح (انتهاء المهلة لم يعد يظهر كـ"بيانات غير صالحة").
- ملفات الأسماء: الأرقام التي تحتوي حروفًا (E001) لم تعد تُسقط أول موظف، والملفات المفصولة بفاصلة منقوطة والأرقام المكتوبة بالأرقام العربية (١٢) أصبحت تُستورد، والملف الخالي من الأسماء يُبلَّغ عنه بدلًا من "أُضيف 0".
- Excel: الأسماء مثل ‎#N/A تبقى نصًا، واسم ورقة الملخص اليومي لم يعد مقطوعًا.
- البحث الذي لا يطابق شيئًا يقول ذلك الآن، والموظف الجديد يبقى ظاهرًا أثناء البحث، والتواريخ في الإعدادات وتقرير السحب تظهر صحيحة بالعربية.
- التحديثات: التثبيت "لي فقط" في أي مجلد أصبح يحدّث نفسه ولا يطلب صلاحيات المسؤول أبدًا، ولم يعد البرنامج يبدأ بعد تثبيت صامت يجريه قسم تقنية المعلومات.

</div>

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
