import os
import time

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_RESHAPER = True
except ImportError:
    HAS_RESHAPER = False

def print_ar(text):
    if HAS_RESHAPER:
        # Reshape characters (connect them)
        reshaped_text = arabic_reshaper.reshape(text)
        # Reorder for RTL display in LTR console
        bidi_text = get_display(reshaped_text)
        print(bidi_text)
    else:
        print(text)

print_ar("------------------------------------------")
print_ar("🛡  جاري التجهيز... (إغلاق النسخ القديمة)")
print_ar("------------------------------------------")

try:
    # Use simple os.system which outputs directly to console (immune to encoding crashes)
    # Use generic message for clean logs
    # print_ar("جاري إغلاق python.exe...") 
    my_pid = os.getpid()
    os.system(f'taskkill /F /FI "PID ne {my_pid}" /IM python.exe >nul 2>&1')
    
    # print_ar("جاري إغلاق pythonw.exe...")
    os.system("taskkill /F /IM pythonw.exe >nul 2>&1")
    
    # Clean sidebar lock file
    import tempfile
    lock_file = os.path.join(tempfile.gettempdir(), "elnagar_sidebar.lock")
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
            print_ar("🔓 تم حذف ملف القفل")
        except:
            pass
    
except Exception as e:
    print(f"Error: {e}")

print_ar("------------------------------------------")
print_ar("🚀  جاري تشغيل برنامج النجار...")
print_ar("------------------------------------------")
print_ar("✅  تم بنجاح. سيتم إغلاق النافذة تلقائياً.")
