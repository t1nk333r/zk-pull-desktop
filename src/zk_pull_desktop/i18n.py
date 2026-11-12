"""English and Arabic texts. Numbers and dates are always shown with Western digits (0-9)."""

LANGUAGES = {"en": "English", "ar": "العربية"}

_current = "en"

TEXTS = {
	# Window and tabs
	"app_title": ("ZK Pull", "ZK Pull"),
	"tab_attendance": ("Attendance", "الحضور"),
	"tab_people": ("People", "الموظفون"),
	"tab_settings": ("Settings", "الإعدادات"),
	# Attendance tab
	"device": ("Device", "الجهاز"),
	"all_devices": ("All devices", "جميع الأجهزة"),
	"from": ("From", "من"),
	"to": ("To", "إلى"),
	"pull": ("Pull from device", "سحب من الجهاز"),
	"export": ("Export…", "تصدير…"),
	"format": ("Format", "الصيغة"),
	"pulling": ("Pulling from {device}…", "جارٍ السحب من {device}…"),
	"pull_failed": ("Could not pull from {device}: {error}", "تعذّر السحب من {device}: {error}"),
	"no_devices": (
		"No devices yet. Add one in Settings.",
		"لا توجد أجهزة بعد. أضف جهازًا من الإعدادات.",
	),
	"shown": ("{count} punches from {start} to {end}", "عدد البصمات: {count} (من {start} إلى {end})"),
	"unnamed_hint": (
		"{count} employee IDs have no name yet (People tab).",
		"عدد أرقام الموظفين بلا اسم: {count} (تبويب الموظفين).",
	),
	"nothing_to_export": ("There are no punches in this period.", "لا توجد بصمات في هذه الفترة."),
	"exported": ("Saved {count} rows to {path}", "تم حفظ الملف في {path} (عدد الصفوف: {count})"),
	"export_failed": ("Could not save the file: {error}", "تعذّر حفظ الملف: {error}"),
	"open_folder": ("Open folder", "فتح المجلد"),
	"open_after_export": ("Open file after export", "فتح الملف بعد التصدير"),
	"busy": (
		"Please wait: the device is still being read.",
		"يرجى الانتظار: لا تزال قراءة الجهاز جارية.",
	),
	"serial_changed": (
		"{device} now reports serial number {new} instead of {old}. That happens when its mainboard is "
		"replaced, but it can also mean a different device is at this IP address. Save its punches "
		"under {device}?",
		"الجهاز {device} يُظهر الآن الرقم التسلسلي {new} بدلًا من {old}. يحدث ذلك عند استبدال اللوحة الأم، "
		"لكنه قد يعني أيضًا وجود جهاز آخر على عنوان IP هذا. هل تريد حفظ بصماته باسم {device}؟",
	),
	"serial_refused": (
		"not saved: serial number {serial} was not accepted",
		"لم تُحفظ: لم يُقبل الرقم التسلسلي {serial}",
	),
	"serial_taken": (
		"not saved: serial number {serial} belongs to {other}. Check the IP addresses in Settings.",
		"لم تُحفظ: الرقم التسلسلي {serial} يخص الجهاز {other}. تحقّق من عناوين IP في الإعدادات.",
	),
	"search_punches": (
		"Search ID, name or department…  (Ctrl+F)",
		"بحث برقم الموظف أو الاسم أو القسم…  (Ctrl+F)",
	),
	"last_pull_label": ("Last pull: {when}", "آخر سحب: {when}"),
	"never_pulled": ("Not pulled yet", "لم يُسحب بعد"),
	"pull_done_one": (
		"{device}: {kept} punches from {start} to {end}, {new} of them new.",
		"{device}: عدد البصمات من {start} إلى {end}: {kept}، منها {new} جديدة.",
	),
	"pull_summary": (
		"Pulled {ok} of {total} devices: {kept} punches from {start} to {end}, {new} of them new.",
		"تم السحب من {ok} من أصل {total} أجهزة: عدد البصمات من {start} إلى {end}: {kept}، منها {new} جديدة.",
	),
	"pull_failures": ("Pull results:\n{devices}", "نتائج السحب:\n{devices}"),
	"empty_no_devices": (
		"No devices yet: add one in Settings.",
		"لا توجد أجهزة بعد: أضف جهازًا من الإعدادات.",
	),
	"empty_no_punches": (
		'No punches in this period. Press "Pull from device" to read the device.',
		'لا توجد بصمات في هذه الفترة. اضغط "سحب من الجهاز" لقراءة الجهاز.',
	),
	"from_after_to": ("The From date is after the To date.", "تاريخ البداية بعد تاريخ النهاية."),
	"export_in_use": (
		"Could not save {path}: the file is open in another program, probably Excel. Close it and try again.",
		"تعذّر حفظ {path}: الملف مفتوح في برنامج آخر، غالبًا Excel. أغلقه ثم حاول مرة أخرى.",
	),
	"layout_log_short": ("Punch log", "سجل البصمات"),
	"layout_daily_short": ("Daily summary", "ملخص يومي"),
	# Columns (also used as export headers)
	"col_user_id": ("Employee ID", "رقم الموظف"),
	"col_name": ("Name", "الاسم"),
	"col_department": ("Department", "القسم"),
	"col_date": ("Date", "التاريخ"),
	"col_time": ("Time", "الوقت"),
	"col_punch": ("Punch type", "نوع البصمة"),
	"col_verify": ("Verified by", "طريقة التحقق"),
	"col_device": ("Device", "الجهاز"),
	"col_first": ("First punch", "أول بصمة"),
	"col_last": ("Last punch", "آخر بصمة"),
	"col_hours": ("Hours", "الساعات"),
	"col_count": ("Punches", "عدد البصمات"),
	# Punch types (device state keys)
	"punch_0": ("Check-in", "حضور"),
	"punch_1": ("Check-out", "انصراف"),
	"punch_2": ("Break-out", "بداية استراحة"),
	"punch_3": ("Break-in", "نهاية استراحة"),
	"punch_4": ("Overtime-in", "دخول عمل إضافي"),
	"punch_5": ("Overtime-out", "خروج عمل إضافي"),
	"punch_other": ("Other ({code})", "أخرى ({code})"),
	# Verification methods
	"verify_0": ("Password", "كلمة المرور"),
	"verify_1": ("Fingerprint", "بصمة الإصبع"),
	"verify_2": ("Card", "البطاقة"),
	"verify_15": ("Face", "بصمة الوجه"),
	"verify_other": ("Other ({code})", "أخرى ({code})"),
	# People tab
	"add": ("Add", "إضافة"),
	"delete": ("Delete", "حذف"),
	"import_device": ("Import names from device", "استيراد الأسماء من الجهاز"),
	"import_file": ("Import from file…", "استيراد من ملف…"),
	"add_unnamed": ("Add IDs without a name", "إضافة الأرقام التي بلا اسم"),
	"imported": ("{count} names added or updated.", "عدد الأسماء المضافة أو المحدّثة: {count}."),
	"import_failed": ("Import failed: {error}", "فشل الاستيراد: {error}"),
	"import_file_hint": (
		"The file needs two columns: employee ID, then name (a header row is fine).",
		"يجب أن يحتوي الملف على عمودين: رقم الموظف ثم الاسم (يمكن أن يكون أول صف عناوين).",
	),
	"file_too_large": ("The file is too large for a names list.", "الملف أكبر من أن يكون قائمة أسماء."),
	"confirm_overwrite": ("{path} already exists. Replace it?", "الملف {path} موجود. هل تريد استبداله؟"),
	"new_user_id": ("Employee ID (as on the device):", "رقم الموظف (كما في الجهاز):"),
	"confirm_delete_person": ("Delete {name}?", "حذف {name}؟"),
	"duplicate_id": ("This employee ID already exists.", "رقم الموظف هذا موجود مسبقًا."),
	# Settings tab
	"devices": ("Devices", "الأجهزة"),
	"device_name": ("Name", "الاسم"),
	"ip": ("IP address", "عنوان IP"),
	"port": ("Port", "المنفذ"),
	"comm_key": ("Comm key", "مفتاح الاتصال"),
	"serial": ("Serial number", "الرقم التسلسلي"),
	"last_pull": ("Last pull", "آخر سحب"),
	"edit": ("Edit", "تعديل"),
	"add_device": ("Add device", "إضافة جهاز"),
	"edit_device": ("Edit device", "تعديل الجهاز"),
	"test": ("Test connection", "اختبار الاتصال"),
	"test_ok": (
		"Connected. Serial {serial}, {punches} punches, {users} users.",
		"تم الاتصال. الرقم التسلسلي {serial}، عدد البصمات {punches}، عدد المستخدمين {users}.",
	),
	"test_failed": ("Could not connect: {error}", "تعذّر الاتصال: {error}"),
	"confirm_delete_device": (
		"Remove {name}? Punches already pulled from it are kept.",
		"إزالة {name}؟ البصمات التي سُحبت منه سابقًا ستبقى محفوظة.",
	),
	"general": ("General", "عام"),
	"language": ("Language", "اللغة"),
	"export_layout": ("Export layout", "شكل التصدير"),
	"layout_log": ("Punch log (one row per punch)", "سجل البصمات (صف لكل بصمة)"),
	"layout_daily": ("Daily summary (first and last punch per day)", "ملخص يومي (أول وآخر بصمة في اليوم)"),
	"header_language": ("Export column headers", "لغة عناوين الأعمدة في التصدير"),
	"export_folder": ("Default export folder", "مجلد التصدير الافتراضي"),
	"browse": ("Browse…", "استعراض…"),
	"data_folder": ("Data folder", "مجلد البيانات"),
	"invalid_device": ("Name and IP address are required.", "الاسم وعنوان IP مطلوبان."),
	"open_data_folder": ("Open data folder", "فتح مجلد البيانات"),
	"open_log": ("Open log", "فتح السجل"),
	"backup": ("Back up database…", "نسخ احتياطي لقاعدة البيانات…"),
	"backup_done": (
		"Backup saved to {path}. To restore it, close ZK Pull and copy it over zk_pull.db in the data folder.",
		"تم حفظ النسخة الاحتياطية في {path}. لاستعادتها، أغلق ZK Pull وانسخها مكان zk_pull.db في مجلد البيانات.",
	),
	"backup_failed": ("Could not back up: {error}", "تعذّر النسخ الاحتياطي: {error}"),
	"about": ("About", "حول البرنامج"),
	"about_text": (
		"Pulls attendance from ZKTeco devices and exports it to Excel or CSV. It only reads from devices.",
		"يسحب سجلات الحضور من أجهزة ZKTeco ويصدّرها إلى Excel أو CSV. يقرأ من الأجهزة فقط.",
	),
	"about_icon": ("App icon by", "أيقونة البرنامج من"),
	# Updates
	"updates": ("Updates", "التحديثات"),
	"check_updates_startup": ("Check for updates at startup", "التحقق من التحديثات عند التشغيل"),
	"check_updates_now": ("Check for updates", "التحقق من التحديثات"),
	"update_available": (
		"Version {version} is available (this is {current}). Install it now? ZK Pull will close and "
		"restart; your data is kept.",
		"الإصدار {version} متاح (الإصدار الحالي {current}). هل تريد تثبيته الآن؟ سيُغلق ZK Pull "
		"ويُعاد تشغيله، وتبقى بياناتك محفوظة.",
	),
	"update_portable": (
		"Version {version} is available (this is {current}). Open the download page?",
		"الإصدار {version} متاح (الإصدار الحالي {current}). هل تريد فتح صفحة التنزيل؟",
	),
	"update_ask_it": (
		"Version {version} is available (this is {current}). ZK Pull is installed for all users, so "
		"updating needs administrator rights: ask IT to run the new installer.",
		"الإصدار {version} متاح (الإصدار الحالي {current}). ZK Pull مثبّت لجميع المستخدمين، لذا يحتاج "
		"التحديث إلى صلاحيات المسؤول: اطلب من قسم تقنية المعلومات تشغيل المثبّت الجديد.",
	),
	"update_none": ("ZK Pull is up to date (version {version}).", "ZK Pull محدّث (الإصدار {version})."),
	"update_failed": ("Could not update: {error}", "تعذّر التحديث: {error}"),
	"update_downloading": ("Downloading version {version}…", "جارٍ تنزيل الإصدار {version}…"),
	"install": ("Install", "تثبيت"),
	"later": ("Later", "لاحقًا"),
	# First run
	"welcome_title": ("Welcome to ZK Pull", "مرحبًا بك في ZK Pull"),
	"welcome_text": (
		"Pull attendance from your ZKTeco devices over the office network and export it to Excel or CSV. "
		"Nothing is ever deleted from the devices.",
		"اسحب سجلات الحضور من أجهزة ZKTeco عبر شبكة المكتب وصدّرها إلى Excel أو CSV. "
		"لا يُحذف أي شيء من الأجهزة إطلاقًا.",
	),
	"first_device": ("Add your first device", "أضف جهازك الأول"),
	"first_names": ("Employee names", "أسماء الموظفين"),
	"first_names_text": (
		"Names make the exports readable. You can import them now from the device, or do it later "
		"from the People tab.",
		"الأسماء تجعل ملفات التصدير مفهومة. يمكنك استيرادها الآن من الجهاز، أو لاحقًا من تبويب الموظفين.",
	),
	"skip": ("Skip", "تخطي"),
	"next": ("Next", "التالي"),
	"finish": ("Finish", "إنهاء"),
	"save": ("Save", "حفظ"),
	"error": ("Error", "خطأ"),
	"err_unreachable": (
		"The device did not answer. Check the IP address and port, that the device is on, and that this "
		"PC is on the same network.",
		"لم يستجب الجهاز. تحقّق من عنوان IP والمنفذ، ومن أن الجهاز يعمل، وأن هذا الحاسوب على الشبكة نفسها.",
	),
	"err_device": ("The device sent unusable data ({detail}).", "أرسل الجهاز بيانات غير صالحة ({detail})."),
	"cancelled": ("Cancelled.", "تم الإلغاء."),
	"cancel": ("Cancel", "إلغاء"),
	"skipped_records": (
		"{count} records on {device} have an impossible date and were left out.",
		"عدد السجلات ذات التاريخ غير الصحيح في {device}: {count}، ولم تُحفظ.",
	),
	"err_comm_key": (
		"The device refused the connection: the comm key is wrong.",
		"رفض الجهاز الاتصال: مفتاح الاتصال غير صحيح.",
	),
	# Periods
	"period": ("Period", "الفترة"),
	"period_today": ("Today", "اليوم"),
	"period_yesterday": ("Yesterday", "أمس"),
	"period_this_week": ("This week", "هذا الأسبوع"),
	"period_this_month": ("This month", "هذا الشهر"),
	"period_last_month": ("Last month", "الشهر الماضي"),
	"period_custom": ("Custom", "مخصص"),
	"search": ("Search…", "بحث…"),
	"choose_device": ("Choose a device", "اختر جهازًا"),
	"restart_language": ("The language will change now.", "سيتم تغيير اللغة الآن."),
}


def set_language(code):
	global _current
	_current = code if code in LANGUAGES else "en"


def language():
	return _current


def is_rtl(code=None):
	return (code or _current) == "ar"


def isolate(value):
	"""Keep a value (date, path, Latin name) in its own direction inside Arabic text.

	Without this, "من 2026-11-01" is shown as "من 01-11-2026".
	"""
	return f"\u2068{value}\u2069" if value != "" else value


def tr(key, lang=None, plain=False, **values):
	"""The text in lang (default: the UI language). plain leaves out the direction marks, for files."""
	en, ar = TEXTS[key]
	if (lang or _current) != "ar":
		return en.format(**values) if values else en
	if plain:
		return ar.format(**values) if values else ar
	return ar.format(**{k: isolate(v) for k, v in values.items()}) if values else ar


def punch_label(code, lang=None, plain=False):
	key = f"punch_{code}"
	return tr(key, lang) if key in TEXTS else tr("punch_other", lang, plain, code=code)


def verify_label(code, lang=None, plain=False):
	key = f"verify_{code}"
	return tr(key, lang) if key in TEXTS else tr("verify_other", lang, plain, code=code)
