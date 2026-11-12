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
	"pull_done": (
		"{device}: {total} punches on the device, {new} new.",
		"{device}: {total} بصمة على الجهاز، منها {new} جديدة.",
	),
	"pull_failed": ("Could not pull from {device}: {error}", "تعذّر السحب من {device}: {error}"),
	"no_devices": (
		"No devices yet. Add one in Settings.",
		"لا توجد أجهزة بعد. أضف جهازًا من الإعدادات.",
	),
	"shown": ("{count} punches from {start} to {end}", "{count} بصمة من {start} إلى {end}"),
	"unnamed_hint": (
		"{count} user IDs have no name yet (People tab).",
		"{count} من المعرّفات بلا اسم بعد (تبويب الموظفين).",
	),
	"nothing_to_export": ("There are no punches in this period.", "لا توجد بصمات في هذه الفترة."),
	"exported": ("Saved {count} rows to {path}", "تم حفظ {count} صفًا في {path}"),
	"export_failed": ("Could not save the file: {error}", "تعذّر حفظ الملف: {error}"),
	"open_folder": ("Open folder", "فتح المجلد"),
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
	"punch_0": ("Check-in", "دخول"),
	"punch_1": ("Check-out", "خروج"),
	"punch_2": ("Break-out", "بداية استراحة"),
	"punch_3": ("Break-in", "نهاية استراحة"),
	"punch_4": ("Overtime-in", "دخول عمل إضافي"),
	"punch_5": ("Overtime-out", "خروج عمل إضافي"),
	"punch_other": ("Other ({code})", "أخرى ({code})"),
	# Verification methods
	"verify_0": ("Password", "كلمة مرور"),
	"verify_1": ("Fingerprint", "بصمة إصبع"),
	"verify_2": ("Card", "بطاقة"),
	"verify_15": ("Face", "الوجه"),
	"verify_other": ("Other ({code})", "أخرى ({code})"),
	# People tab
	"add": ("Add", "إضافة"),
	"delete": ("Delete", "حذف"),
	"import_device": ("Import names from device", "استيراد الأسماء من الجهاز"),
	"import_file": ("Import from file…", "استيراد من ملف…"),
	"add_unnamed": ("Add IDs without a name", "إضافة المعرّفات بلا اسم"),
	"imported": ("{count} names added or updated.", "تمت إضافة أو تحديث {count} اسمًا."),
	"import_failed": ("Import failed: {error}", "فشل الاستيراد: {error}"),
	"import_file_hint": (
		"The file needs two columns: employee ID, then name (a header row is fine).",
		"يجب أن يحتوي الملف على عمودين: رقم الموظف ثم الاسم (يمكن أن يكون أول صف عناوين).",
	),
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
	"test": ("Test connection", "اختبار الاتصال"),
	"test_ok": (
		"Connected. Serial {serial}, {punches} punches, {users} users.",
		"تم الاتصال. الرقم التسلسلي {serial}، {punches} بصمة، {users} مستخدم.",
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
	"skip": ("Skip", "تخطٍّ"),
	"next": ("Next", "التالي"),
	"finish": ("Finish", "إنهاء"),
	"cancel": ("Cancel", "إلغاء"),
	"save": ("Save", "حفظ"),
	"error": ("Error", "خطأ"),
	"err_unreachable": (
		"The device did not answer. Check the IP address and port, that the device is on, and that this "
		"PC is on the same network.",
		"لم يستجب الجهاز. تحقّق من عنوان IP والمنفذ، ومن أن الجهاز يعمل، وأن هذا الحاسوب على الشبكة نفسها.",
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


def tr(key, lang=None, **values):
	en, ar = TEXTS[key]
	if (lang or _current) != "ar":
		return en.format(**values) if values else en
	return ar.format(**{k: isolate(v) for k, v in values.items()}) if values else ar


def punch_label(code, lang=None):
	key = f"punch_{code}"
	return tr(key, lang) if key in TEXTS else tr("punch_other", lang, code=code)


def verify_label(code, lang=None):
	key = f"verify_{code}"
	return tr(key, lang) if key in TEXTS else tr("verify_other", lang, code=code)
