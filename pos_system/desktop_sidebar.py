"""
🚀 Elnagar Print - Command Center Sidebar
Revolutionary UI Design v2.0
Premium Dark Theme with Glassmorphism
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import threading
import time
from PIL import Image, ImageTk
import os
import sys
import ctypes
import json
import webbrowser
import subprocess

import database
from file_ops_engine import FileOpsEngine

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    dnd_avail = True
except ImportError:
    dnd_avail = False

def hide_taskbar_icon(window):
    try:
        # Get the HWND
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        # GWL_EXSTYLE = -20
        # WS_EX_TOOLWINDOW = 0x00000080 (Hides from Alt-Tab and Taskbar)
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        style = style | 0x00000080
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
    except Exception as e:
        print(f"Taskbar Hide Error: {e}")

# ═══════════════════════════════════════════════════════════════════
# 🎨 DESIGN SYSTEM - Premium Dark Theme
# ═══════════════════════════════════════════════════════════════════

class DesignSystem:
    """Centralized Design Tokens for consistent styling."""
    
    # Color Palette (Premium Dark/Slate Theme)
    BG_DEEP = "#0F172A"        # Slate 900 (Main Background)
    BG_CARD = "#1E293B"        # Slate 800 (Card Background)
    BG_INPUT = "#334155"       # Slate 700 (Input Field Background)
    
    # Accents
    ACCENT_PRIMARY = "#3B82F6" # Blue 500 (Primary Action)
    ACCENT_SECONDARY = "#8B5CF6" # Violet 500 (Secondary)
    ACCENT_SUCCESS = "#10B981" # Emerald 500 (Success)
    ACCENT_WARNING = "#F59E0B" # Amber 500 (Warning)
    
    # Text
    TEXT_PRIMARY = "#F8FAFC"   # Slate 50 (Main Text)
    TEXT_SECONDARY = "#CBD5E1" # Slate 300 (Subtext)
    TEXT_MUTED = "#64748B"     # Slate 500 (Muted)
    
    # Borders & UI
    BORDER_SUBTLE = "#334155"  # Slate 700
    BG_HOVER = "#334155"       # Hover state background
    
    # Typography (with fallbacks)
    FONT_FAMILY = "Cairo"      # Preferred Arabic font
    FONT_FALLBACK = "Segoe UI" # Windows fallback
    
    # Sizing
    CORNER_RADIUS_LG = 15
    CORNER_RADIUS_MD = 10
    CORNER_RADIUS_SM = 6
    
    @classmethod
    def get_font(cls, size=12, weight="normal"):
        """Get font with fallback support."""
        try:
            return ctk.CTkFont(family=cls.FONT_FAMILY, size=size, weight=weight)
        except:
            return ctk.CTkFont(family=cls.FONT_FALLBACK, size=size, weight=weight)

DS = DesignSystem  # Alias for convenience

# ═══════════════════════════════════════════════════════════════════
# 🎴 REUSABLE COMPONENTS
# ═══════════════════════════════════════════════════════════════════

class GlassCard(ctk.CTkFrame):
    """Glassmorphism-style card container."""
    def __init__(self, master, **kwargs):
        kwargs.setdefault('fg_color', DS.BG_CARD)
        kwargs.setdefault('corner_radius', DS.CORNER_RADIUS_LG)
        kwargs.setdefault('border_width', 1)
        kwargs.setdefault('border_color', DS.BORDER_SUBTLE)
        super().__init__(master, **kwargs)

class PremiumButton(ctk.CTkButton):
    """Premium styled button with hover effects."""
    def __init__(self, master, text="", variant="primary", **kwargs):
        colors = {
            "primary": (DS.ACCENT_PRIMARY, "#1D4ED8"),
            "secondary": (DS.BG_INPUT, DS.BG_HOVER),
            "success": (DS.ACCENT_SUCCESS, "#059669"),
            "ghost": ("transparent", DS.BG_HOVER)
        }
        fg, hover = colors.get(variant, colors["primary"])
        text_col = "#FFFFFF" if variant in ["primary", "success"] else DS.TEXT_PRIMARY
        
        kwargs.setdefault('font', DS.get_font(12, "bold"))
        kwargs.setdefault('fg_color', fg)
        kwargs.setdefault('hover_color', hover)
        kwargs.setdefault('corner_radius', DS.CORNER_RADIUS_SM)
        kwargs.setdefault('text_color', text_col)
        super().__init__(master, text=text, **kwargs)

class PremiumEntry(ctk.CTkEntry):
    def __init__(self, master, placeholder="", **kwargs):
        kwargs.setdefault('font', DS.get_font(12))
        kwargs.setdefault('fg_color', DS.BG_INPUT)
        kwargs.setdefault('border_width', 2)
        kwargs.setdefault('border_color', DS.BORDER_SUBTLE)
        kwargs.setdefault('corner_radius', DS.CORNER_RADIUS_SM)
        kwargs.setdefault('placeholder_text_color', DS.TEXT_MUTED)
        kwargs.setdefault('text_color', DS.TEXT_PRIMARY)
        super().__init__(master, placeholder_text=placeholder, **kwargs)

class PremiumLabel(ctk.CTkLabel):
    def __init__(self, master, text="", variant="primary", **kwargs):
        colors = {"primary": DS.TEXT_PRIMARY, "secondary": DS.TEXT_SECONDARY, "muted": DS.TEXT_MUTED, "accent": DS.ACCENT_PRIMARY, "success": DS.ACCENT_SUCCESS}
        kwargs.setdefault('font', DS.get_font(12))
        kwargs.setdefault('text_color', colors.get(variant, DS.TEXT_PRIMARY))
        kwargs.setdefault('anchor', "e")
        super().__init__(master, text=text, **kwargs)

# ═══════════════════════════════════════════════════════════════════
# 💰 FINANCIAL MODALS
# ═══════════════════════════════════════════════════════════════════

class PaymentModal(ctk.CTkToplevel):
    def __init__(self, master, client_id, on_save):
        super().__init__(master)
        self.client_id = client_id
        self.on_save = on_save
        self.title("تسجيل دفعة | Payment")
        self.geometry("300x250")
        self.configure(fg_color=DS.BG_DEEP)
        self.attributes('-topmost', True)
        
        # UI
        PremiumLabel(self, text="المبلغ المدفوع", font=DS.get_font(12, "bold")).pack(pady=(10, 5))
        self.entry = PremiumEntry(self, placeholder="0.00")
        self.entry.pack(pady=5, padx=20, fill="x")
        
        PremiumLabel(self, text="ملاحظات الدفعة", font=DS.get_font(12, "bold")).pack(pady=(10, 5))
        self.note_entry = PremiumEntry(self, placeholder="دفعة من الحساب")
        self.note_entry.pack(pady=5, padx=20, fill="x")
        
        PremiumButton(self, text="حفظ الدفعة", variant="success", command=self._save).pack(pady=20, padx=20, fill="x")
        
    def _save(self):
        try:
            amount = float(self.entry.get())
            note = self.note_entry.get().strip() or "دفعة من الحساب"
            if database.update_client_balance(self.client_id, amount, note):
                self.on_save()
                self.destroy()
        except ValueError: pass

class StatementModal(ctk.CTkToplevel):
    def __init__(self, master, client_id):
        super().__init__(master)
        self.client_id = client_id
        self.title("كشف حساب | Account Statement")
        self.geometry("450x650")
        self.configure(fg_color=DS.BG_DEEP)
        self.attributes('-topmost', True)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self.header = ctk.CTkFrame(self, fg_color=DS.BG_CARD)
        self.header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        self.lbl_name = PremiumLabel(self.header, text="...", font=DS.get_font(14, "bold"))
        self.lbl_name.pack(pady=5)
        
        self.lbl_balance = PremiumLabel(self.header, text="...", variant="accent", font=DS.get_font(12))
        self.lbl_balance.pack(pady=5)
        
        # Tabs for Products and Transactions
        self.tabview = ctk.CTkTabview(self, fg_color=DS.BG_CARD, corner_radius=DS.CORNER_RADIUS_MD)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        self.tab_products = self.tabview.add("📦 المنتجات")
        self.tab_transactions = self.tabview.add("📜 السجل المالي")
        
        self.scroll_products = ctk.CTkScrollableFrame(self.tab_products, fg_color="transparent")
        self.scroll_products.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.scroll_transactions = ctk.CTkScrollableFrame(self.tab_transactions, fg_color="transparent")
        self.scroll_transactions.pack(fill="both", expand=True, padx=5, pady=5)
        
        footer = ctk.CTkFrame(self, fg_color=DS.BG_CARD)
        footer.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        PremiumButton(footer, text="تسجيل دفعة", variant="success", command=self._open_payment).pack(fill="x", padx=10, pady=5)
        
        self._load_data()
        
    def _load_data(self):
        data = database.get_client_statement_data(self.client_id)
        if not data: return
        client = data.get('client', {})
        summary = data.get('summary', {})
        self.lbl_name.configure(text=client.get('name', 'عميل'))
        
        for w in self.header.winfo_children():
            if w not in [self.lbl_name, self.lbl_balance]: w.destroy()
            
        stats_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        stats_frame.pack(fill="x", padx=10, pady=5)
        
        def add_stat(label, val, color=DS.TEXT_PRIMARY):
            f = ctk.CTkFrame(stats_frame, fg_color="transparent")
            f.pack(side="right", expand=True)
            PremiumLabel(f, text=label, variant="muted", font=DS.get_font(9)).pack()
            PremiumLabel(f, text=f"{val:,.0f}", text_color=color, font=DS.get_font(11, "bold")).pack()

        add_stat("المديونية", summary.get('total_debt', 0), DS.ACCENT_WARNING)
        add_stat("تحت التجهيز", summary.get('processing_debt', 0), "#f59e0b")
        add_stat("جاهز", summary.get('executed_debt', 0), DS.ACCENT_SUCCESS)
        add_stat("إجمالي المسحوبات", summary.get('total_sales', 0))
        
        # Clear tabs content
        for w in self.scroll_products.winfo_children(): w.destroy()
        for w in self.scroll_transactions.winfo_children(): w.destroy()
        
        # 1. Populate Products Tab
        grouped_items = data.get('grouped_items', {})
        
        def add_grouped_section(title, items, color):
            if not items: return
            # Section Label
            ctk.CTkLabel(self.scroll_products, text=title, font=DS.get_font(11, "bold"), text_color=color).pack(anchor="e", padx=5, pady=(10, 5))
            for item in items:
                card = ctk.CTkFrame(self.scroll_products, fg_color=DS.BG_INPUT, corner_radius=6)
                card.pack(fill="x", pady=2, padx=2)
                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill="x", padx=8, pady=5)
                
                # Total amount on the left
                ctk.CTkLabel(row, text=f"{item.get('total', 0):,.2f} ج.م", font=DS.get_font(12, "bold"), text_color=DS.ACCENT_PRIMARY).pack(side="left")
                
                # Product info on the right
                info_frame = ctk.CTkFrame(row, fg_color="transparent")
                info_frame.pack(side="right", fill="x", expand=True)
                PremiumLabel(info_frame, text=item.get('product_name', 'منتج'), font=DS.get_font(11, "bold")).pack(anchor="e")
                PremiumLabel(info_frame, text=f"العدد: {item.get('qty', 0)} | سعر الوحدة: {item.get('unit_price', 0):,.2f} ج.م", variant="muted", font=DS.get_font(9)).pack(anchor="e")
                
        add_grouped_section("⏳ جاري التجهيز", grouped_items.get('under_prep', []), "#f59e0b")
        add_grouped_section("✅ جاهز للتسليم", grouped_items.get('ready', []), DS.ACCENT_SUCCESS)
        add_grouped_section("📦 تم التسليم", grouped_items.get('delivered', []), DS.TEXT_SECONDARY)
        
        if not grouped_items.get('under_prep') and not grouped_items.get('ready') and not grouped_items.get('delivered'):
            PremiumLabel(self.scroll_products, text="لا توجد منتجات مسجلة", variant="muted", font=DS.get_font(10)).pack(pady=20)
            
        # 2. Populate Transactions Tab
        for t in data['transactions']:
            card = ctk.CTkFrame(self.scroll_transactions, fg_color=DS.BG_INPUT, corner_radius=6)
            card.pack(fill="x", pady=2, padx=2)
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=5)
            amt_color = DS.ACCENT_SUCCESS if t['type'].lower() in ['payment', 'income'] else DS.TEXT_PRIMARY
            prefix = "+" if t['type'].lower() in ['payment', 'income'] else "-"
            ctk.CTkLabel(row, text=f"{prefix}{t['amount']:,.2f}", font=DS.get_font(12, "bold"), text_color=amt_color).pack(side="left")
            info_frame = ctk.CTkFrame(row, fg_color="transparent")
            info_frame.pack(side="right", fill="x", expand=True)
            type_text = "دفعة مادية" if t['type'].lower() in ['payment', 'income'] else "سحب آجل"
            PremiumLabel(info_frame, text=type_text, font=DS.get_font(10, "bold")).pack(anchor="e")
            if t.get('notes'): PremiumLabel(info_frame, text=t['notes'], variant="muted", font=DS.get_font(9)).pack(anchor="e")
            ctk.CTkLabel(card, text=t['date'], font=DS.get_font(8), text_color=DS.TEXT_MUTED).pack(anchor="w", padx=10, pady=(0, 5))

    def _open_payment(self):
        PaymentModal(self, self.client_id, self._load_data)

# ═══════════════════════════════════════════════════════════════════
# 📋 ORDER CARD COMPONENT
# ═══════════════════════════════════════════════════════════════════

class OrderCard(GlassCard):
    def __init__(self, master, order_data, controller):
        super().__init__(master, corner_radius=DS.CORNER_RADIUS_SM) 
        self.order = order_data
        self.controller = controller
        self.grid_columnconfigure(1, weight=1)
        
        status_colors = {'Under Preparation': DS.ACCENT_WARNING, 'Ready': DS.ACCENT_SUCCESS, 'Delivered': "#3b82f6"}
        status_color = status_colors.get(order_data.get('status', ''), DS.ACCENT_WARNING)
        self.indicator = ctk.CTkFrame(self, width=4, fg_color=status_color, corner_radius=2)
        self.indicator.grid(row=0, column=0, rowspan=4, sticky="ns", padx=(4, 4), pady=4)
        
        header_frame = ctk.CTkFrame(self, fg_color="transparent", height=20)
        header_frame.grid(row=0, column=1, sticky="ew", pady=(2, 0), padx=2)
        PremiumLabel(header_frame, text=f"#{order_data['id']}", variant="muted", font=DS.get_font(10)).pack(side="left")
        price = order_data.get('total_amount', 0)
        PremiumLabel(header_frame, text=f"{price:,.2f} ج.م", variant="accent", font=DS.get_font(12, "bold")).pack(side="right")
        
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.grid(row=1, column=1, sticky="ew", pady=1, padx=2)
        if order_data.get('items'):
            item = order_data['items'][0]
            prod_name = item.get('product_name', 'منتج')[:25]
            PremiumLabel(content_frame, text=prod_name, variant="primary", font=DS.get_font(12, "bold"), anchor="e").pack(side="right", fill="x", expand=True)
            
        client = order_data.get('client_name', 'عميل')[:20]
        PremiumLabel(self, text=f"👤 {client}", variant="secondary", font=DS.get_font(10), anchor="e").grid(row=2, column=1, sticky="ew", padx=5)
        
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=1, sticky="ew", pady=(2, 2), padx=2)
        btn_size = 32
        PremiumButton(actions, text="📂", variant="secondary", width=btn_size, height=btn_size, font=DS.get_font(16), command=self._open_folder).pack(side="left", padx=2)
        self.btn_gallery = PremiumButton(actions, text="🖼️", variant="secondary", width=btn_size, height=btn_size, font=DS.get_font(16), command=self._toggle_gallery)
        self.btn_gallery.pack(side="left", padx=2)
        
        next_status = None
        if order_data.get('status') == 'Under Preparation': next_status = 'Ready'
        elif order_data.get('status') == 'Ready': next_status = 'Delivered'
        if next_status:
            PremiumButton(actions, text="➡", variant="success", width=btn_size, height=btn_size, font=DS.get_font(18, "bold"), command=lambda: controller.update_status(order_data['id'], next_status)).pack(side="left", padx=(10, 2))
            
        self.gallery_frame = ctk.CTkFrame(self, fg_color=DS.BG_INPUT, corner_radius=0)
        self.gallery_frame.grid(row=4, column=1, sticky="ew", padx=2, pady=0)
        self.gallery_frame.grid_remove()
        self.gallery_loaded = False

    def _open_folder(self):
        try:
            path = self.order.get('local_image_path')
            if path and os.path.exists(path): os.startfile(path)
        except: pass

    def _toggle_gallery(self):
        if self.gallery_frame.grid_info():
            self.gallery_frame.grid_remove()
            self.configure(fg_color=DS.BG_CARD)
        else:
            self.gallery_frame.grid(row=4, column=1, sticky="ew", padx=2, pady=(5, 5))
            self.configure(fg_color="#eff6ff")
            if not self.gallery_loaded:
                self._load_gallery_images()
                self.gallery_loaded = True

    def _load_gallery_images(self):
        root_path = self.order.get('local_image_path')
        head = ctk.CTkFrame(self.gallery_frame, fg_color="transparent")
        head.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(head, text="اسحب للفوتوشوب 👇", font=DS.get_font(10), text_color=DS.ACCENT_PRIMARY).pack(side="right")
        img_container = ctk.CTkScrollableFrame(self.gallery_frame, height=140, fg_color="transparent", orientation="horizontal")
        img_container.pack(fill="x", expand=True, padx=2, pady=2)
        if not root_path or not os.path.exists(root_path): return
        
        valid_exts = ('.jpg', '.jpeg', '.png', '.psd')
        images_found = []
        for root, dirs, files in os.walk(root_path):
            for f in files:
                if f.lower().endswith(valid_exts): images_found.append(os.path.join(root, f))
        
        for img_path in images_found:
            try:
                pil_img = Image.open(img_path)
                pil_img.thumbnail((90, 90))
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
                wrapper = ctk.CTkFrame(img_container, fg_color="white", corner_radius=6)
                wrapper.pack(side="right", padx=6, pady=4)
                btn = ctk.CTkButton(wrapper, image=ctk_img, text="", width=pil_img.size[0], height=pil_img.size[1], fg_color="transparent", command=lambda p=img_path: self._copy_image_file(p))
                btn.pack(padx=2, pady=(2, 0))
                if dnd_avail:
                    btn.drag_source_register(1, DND_FILES)
                    btn.dnd_bind('<<DragInitCmd>>', lambda e, p=img_path: ('copy', DND_FILES, f"{{{os.path.abspath(p)}}}"))
            except: pass

    def _copy_image_file(self, path):
        import win32clipboard
        from PIL import Image
        import io
        try:
            image = Image.open(path)
            output = io.BytesIO()
            image.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
        except: pass

# ═══════════════════════════════════════════════════════════════════
# 📋 ORDERS TAB
# ═══════════════════════════════════════════════════════════════════

class OrdersTab(ctk.CTkFrame):
    def __init__(self, master, main_window):
        super().__init__(master, fg_color="transparent")
        self.main_window = main_window
        self.last_hash = ""
        self.sub_tabs = ctk.CTkTabview(self, corner_radius=DS.CORNER_RADIUS_MD, fg_color=DS.BG_CARD)
        self.sub_tabs.pack(fill="both", expand=True)
        self.tab_prep = self.sub_tabs.add("⏳ تجهيز")
        self.tab_ready = self.sub_tabs.add("✅ جاهز")
        self.tab_delivered = self.sub_tabs.add("📦 تسليم")
        self.scroll_prep = ctk.CTkScrollableFrame(self.tab_prep, fg_color="transparent")
        self.scroll_prep.pack(fill="both", expand=True)
        self.scroll_ready = ctk.CTkScrollableFrame(self.tab_ready, fg_color="transparent")
        self.scroll_ready.pack(fill="both", expand=True)
        self.scroll_delivered = ctk.CTkScrollableFrame(self.tab_delivered, fg_color="transparent")
        self.scroll_delivered.pack(fill="both", expand=True)
        self.auto_refresh()
    
    def auto_refresh(self):
        self.refresh_data()
        self.after(5000, self.auto_refresh)
    
    def refresh_data(self):
        try:
            orders = database.get_kanban_orders()
            current_hash = str([(o['id'], o['status']) for o in orders])
            if current_hash == self.last_hash: return
            self.last_hash = current_hash
            for s in [self.scroll_prep, self.scroll_ready, self.scroll_delivered]:
                for w in s.winfo_children(): w.destroy()
            for o in orders:
                target = self.scroll_prep if o['status'] == 'Under Preparation' else self.scroll_ready if o['status'] == 'Ready' else self.scroll_delivered
                OrderCard(target, o, self).pack(fill="x", pady=2)
        except: pass
    
    def update_status(self, order_id, new_status):
        threading.Thread(target=lambda: database.update_order_status(order_id, new_status), daemon=True).start()
        self.after(200, self.refresh_data)

# ═══════════════════════════════════════════════════════════════════
# ➕ ADD ORDER TAB
# ═══════════════════════════════════════════════════════════════════

class AddOrderTab(ctk.CTkFrame):
    def __init__(self, master, main_window):
        super().__init__(master, fg_color="transparent")
        container = GlassCard(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        PremiumLabel(container, text="إضافة طلب جديد", font=DS.get_font(16, "bold")).pack(pady=15)
        
        self.client_var = ctk.StringVar()
        self.client_combo = ctk.CTkComboBox(container, variable=self.client_var, values=[c['name'] for c in database.get_all_clients()])
        self.client_combo.pack(fill="x", padx=20, pady=5)
        
        self.product_var = ctk.StringVar()
        self.product_combo = ctk.CTkComboBox(container, variable=self.product_var, values=[p['name'] for p in database.get_all_products()])
        self.product_combo.pack(fill="x", padx=20, pady=5)
        
        self.price_entry = PremiumEntry(container, placeholder="السعر")
        self.price_entry.pack(fill="x", padx=20, pady=5)
        
        self.qty_entry = PremiumEntry(container, placeholder="العدد")
        self.qty_entry.insert(0, "1")
        self.qty_entry.pack(fill="x", padx=20, pady=5)

        self.delivery_date_entry = PremiumEntry(container, placeholder="تاريخ التسليم YYYY-MM-DD")
        self.delivery_date_entry.insert(0, time.strftime("%Y-%m-%d"))
        self.delivery_date_entry.pack(fill="x", padx=20, pady=5)

        self.custom_notes_entry = PremiumEntry(container, placeholder="ملاحظات التشغيل / الأسماء المحفورة")
        self.custom_notes_entry.pack(fill="x", padx=20, pady=5)
        
        PremiumButton(container, text="💾 حفظ الطلب", command=self._save_order).pack(pady=20, padx=20, fill="x")

    def _save_order(self):
        try:
            client = database.get_db_connection().execute("SELECT * FROM clients WHERE name=?", (self.client_var.get(),)).fetchone()
            product = database.get_db_connection().execute("SELECT * FROM products WHERE name=?", (self.product_var.get(),)).fetchone()
            if client and product:
                total = float(self.price_entry.get()) * int(self.qty_entry.get())
                items = [{'id': product['id'], 'name': product['name'], 'qty': int(self.qty_entry.get()), 'price': float(self.price_entry.get()), 'total': total}]
                custom_notes = self.custom_notes_entry.get().strip()
                database.save_order_transaction(
                    client['id'],
                    total,
                    0,
                    total,
                    0,
                    total,
                    items,
                    "None",
                    custom_notes,
                    self.delivery_date_entry.get().strip() or None,
                    custom_notes,
                )
        except: pass

# ═══════════════════════════════════════════════════════════════════
# 👥 CRM TAB
# ═══════════════════════════════════════════════════════════════════

class CRMTab(ctk.CTkFrame):
    def __init__(self, master, main_window):
        super().__init__(master, fg_color="transparent")
        self.search_var = ctk.StringVar()
        self.search_var.trace("w", self._filter_clients)
        PremiumEntry(self, textvariable=self.search_var, placeholder="🔍 بحث عن عميل...").pack(fill="x", pady=5)
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)
        self.refresh_data()
        
    def refresh_data(self):
        self.all_clients = database.get_all_clients()
        self._filter_clients()

    def _filter_clients(self, *args):
        query = self.search_var.get().lower()
        for w in self.scroll.winfo_children(): w.destroy()
        for c in self.all_clients:
            if query in c['name'].lower(): self._create_card(c)
                
    def _create_card(self, client):
        card = GlassCard(self.scroll, corner_radius=DS.CORNER_RADIUS_SM)
        card.pack(fill="x", pady=2)
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        PremiumLabel(header, text=client['name'], font=DS.get_font(12, "bold")).pack(side="right")
        bal = client.get('balance', 0)
        ctk.CTkLabel(header, text=f"{bal:,.0f} ج.م", fg_color=DS.ACCENT_WARNING if bal > 0 else DS.ACCENT_SUCCESS, corner_radius=4, text_color="white").pack(side="left")
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=5, pady=5)
        PremiumButton(actions, text="كشف حساب", variant="secondary", width=70, command=lambda: StatementModal(self.winfo_toplevel(), client['id'])).pack(side="right", padx=2)
        PremiumButton(actions, text="💵 دفع سريع", variant="success", width=70, command=lambda: PaymentModal(self.winfo_toplevel(), client['id'], self.refresh_data)).pack(side="right", padx=2)

# ═══════════════════════════════════════════════════════════════════
# 📁 FILES TAB
# ═══════════════════════════════════════════════════════════════════

class FilesTab(ctk.CTkFrame):
    def __init__(self, master, main_window):
        super().__init__(master, fg_color="transparent")
        self.roots = [r"H:\Orders", os.getcwd()]
        self.tree = ttk.Treeview(self, show="tree")
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)
        self.tree.bind("<Double-1>", self._on_double_click)
        self._populate_tree()
    
    def _populate_tree(self):
        for r in self.roots:
            if os.path.exists(r):
                node = self.tree.insert("", "end", text=f"📁 {os.path.basename(r)}", values=[r])
                try:
                    for item in os.listdir(r)[:20]: self.tree.insert(node, "end", text=f"📄 {item}", values=[os.path.join(r, item)])
                except: pass
    
    def _on_double_click(self, event):
        try:
            path = self.tree.item(self.tree.selection()[0], "values")[0]
            if os.path.exists(path): os.startfile(path)
        except: pass

# ═══════════════════════════════════════════════════════════════════
# 📝 NOTES TAB
# ═══════════════════════════════════════════════════════════════════

class NotesTab(ctk.CTkFrame):
    def __init__(self, master, main_window):
        super().__init__(master, fg_color="transparent")
        self.notes_file = "sidebar_notes.json"
        self.entry = PremiumEntry(self, placeholder="✍️ إضافة ملاحظة...")
        self.entry.pack(fill="x", pady=5)
        self.entry.bind("<Return>", self._add_note)
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)
        self.notes = []
        self._load_notes()
        
    def _load_notes(self):
        if os.path.exists(self.notes_file):
            with open(self.notes_file, "r", encoding="utf-8") as f: self.notes = json.load(f)
        self._render_notes()

    def _save_notes(self):
        with open(self.notes_file, "w", encoding="utf-8") as f: json.dump(self.notes, f, ensure_ascii=False)
            
    def _add_note(self, event=None):
        content = self.entry.get().strip()
        if content:
            from datetime import datetime
            self.notes.insert(0, {"content": content, "date": datetime.now().strftime("%d/%m %I:%M %p"), "checked": False})
            self._save_notes(); self._render_notes(); self.entry.delete(0, 'end')
            
    def _render_notes(self):
        for w in self.scroll.winfo_children(): w.destroy()
        for i, n in enumerate(self.notes): self._draw_card(i, n)
            
    def _draw_card(self, index, note):
        bg = {"yellow": "#fef9c3", "blue": "#dbeafe", "green": "#dcfce7", "red": "#fee2e2"}.get(note.get('color_name'), DS.BG_CARD)
        card = ctk.CTkFrame(self.scroll, fg_color=bg, border_width=1, border_color=DS.BORDER_SUBTLE)
        card.pack(fill="x", pady=4, padx=5)
        
        ctk.CTkButton(card, text="☑️" if note.get('checked') else "⬜", width=25, fg_color="transparent", command=lambda: self._toggle_check(index)).pack(side="right")
        
        box = ctk.CTkTextbox(card, font=DS.get_font(11), fg_color="transparent", height=60)
        box.pack(side="right", fill="x", expand=True); box.insert("1.0", note['content'])
        box.bind("<FocusOut>", lambda e, i=index, b=box: self._save_edit(i, b))
        
        footer = ctk.CTkFrame(card, fg_color="transparent", height=24)
        footer.pack(side="bottom", fill="x")
        PremiumButton(footer, text="🗑️", variant="secondary", width=24, command=lambda: self._delete(index)).pack(side="right")
        PremiumButton(footer, text="📋", variant="secondary", width=24, command=lambda: self._copy(note['content'])).pack(side="right")
        for c in ["yellow", "blue", "green", "red"]:
            ctk.CTkButton(footer, text="", width=12, height=12, fg_color=c, command=lambda i=index, n=c: self._color(i, n)).pack(side="right", padx=1)

    def _save_edit(self, i, box):
        self.notes[i]['content'] = box.get("1.0", "end-1c").strip(); self._save_notes()
    def _copy(self, t): self.master.clipboard_clear(); self.master.clipboard_append(t)
    def _color(self, i, n): self.notes[i]['color_name'] = n; self._save_notes(); self._render_notes()
    def _toggle_check(self, i): self.notes[i]['checked'] = not self.notes[i].get('checked'); self._save_notes(); self._render_notes()
    def _delete(self, i): del self.notes[i]; self._save_notes(); self._render_notes()

# ═══════════════════════════════════════════════════════════════════
# 🔴 LASER OPS TAB
# ═══════════════════════════════════════════════════════════════════

class LaserOpsTab(ctk.CTkFrame):
    def __init__(self, master, main_window):
        super().__init__(master, fg_color="transparent")
        self.main_window = main_window
        header = GlassCard(self)
        header.pack(fill="x", padx=8, pady=(8, 4))
        PremiumLabel(header, text="غرفة عمليات الليزر", font=DS.get_font(15, "bold")).pack(anchor="e", padx=12, pady=(10, 2))
        PremiumLabel(header, text="استخدم لوحة Kanban الجديدة لتشغيل الـMES والتصنيف الذكي للطلبات الحالية.", variant="secondary", font=DS.get_font(11), wraplength=360, justify="right").pack(anchor="e", padx=12, pady=(0, 10))
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(0, 12))
        PremiumButton(actions, text="🔴 فتح غرفة عمليات الليزر", command=self._open_new_laser_ops).pack(side="right", padx=4)
        PremiumButton(actions, text="تحديث الملخص", variant="secondary", command=self.refresh_data).pack(side="right", padx=4)
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=DS.BG_CARD)
        self.scroll.pack(fill="both", expand=True)
        self.refresh_data()

    def _open_new_laser_ops(self):
        try:
            script_path = os.path.join(os.path.dirname(__file__), "laser_ops.py")
            python_cmd = sys.executable or "python"
            subprocess.Popen([python_cmd, script_path], cwd=os.path.dirname(__file__))
        except:
            pass
    def refresh_data(self):
        for w in self.scroll.winfo_children(): w.destroy()
        try:
            for item in database.get_laser_queue_summary():
                row = ctk.CTkFrame(self.scroll, fg_color=DS.BG_DEEP); row.pack(fill="x", pady=2)
                PremiumLabel(row, text=item['product_name']).pack(side="right", padx=10)
                ctk.CTkLabel(row, text=str(item['total_qty']), fg_color=DS.ACCENT_PRIMARY).pack(side="left", padx=10)
        except: pass

# ═══════════════════════════════════════════════════════════════════
# 🔘 FLOATING ICON
# ═══════════════════════════════════════════════════════════════════

class FloatingIcon(ctk.CTkToplevel):
    def __init__(self, master, toggle_callback):
        super().__init__(master)
        self.toggle_callback = toggle_callback
        self.overrideredirect(True); self.attributes('-topmost', True); self.attributes('-alpha', 0.95)
        self.size = 42
        self.geometry(f"{self.size}x{self.size}+{self.winfo_screenwidth()-52}+{self.winfo_screenheight()//2}")
        self.btn = ctk.CTkButton(self, text="EP", width=self.size, height=self.size, corner_radius=self.size//2, command=self._on_click)
        self.btn.pack(fill="both")
        self._drag_data = {"x": 0, "y": 0}
        self.btn.bind("<ButtonPress-1>", self._start_drag)
        self.btn.bind("<B1-Motion>", self._do_drag)
        self.btn.bind("<ButtonRelease-1>", self._stop_drag)
    
    def _on_click(self):
        if not getattr(self, '_dragged', False): self.toggle_callback()
    def _start_drag(self, event):
        self._drag_data = {"x": event.x, "y": event.y}; self._dragged = False
    def _do_drag(self, event):
        dx, dy = event.x - self._drag_data["x"], event.y - self._drag_data["y"]
        if abs(dx) > 3 or abs(dy) > 3: self._dragged = True
        x, y = self.winfo_x() + dx, self.winfo_y() + dy
        self.geometry(f"+{max(0, min(x, self.winfo_screenwidth()-self.size))}+{max(0, min(y, self.winfo_screenheight()-self.size))}")
    def _stop_drag(self, event): pass

# ═══════════════════════════════════════════════════════════════════
# 📱 MAIN SIDEBAR WINDOW
# ═══════════════════════════════════════════════════════════════════

class MainSidebar(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True); self.attributes('-topmost', True)
        self.width = 420; self.docked_side = "right"
        self._update_position(); self.configure(fg_color=DS.BG_DEEP)
        
        self.resize_handle = ctk.CTkFrame(self, width=4, fg_color="transparent", cursor="sb_h_double_arrow")
        self.resize_handle.place(relx=0, rely=0, relheight=1)
        self.resize_handle.bind("<ButtonPress-1>", self._start_resize)
        self.resize_handle.bind("<B1-Motion>", self._do_resize)
        
        header = ctk.CTkFrame(self, height=60, fg_color=DS.BG_CARD)
        header.pack(fill="x")
        PremiumButton(header, text="◀", width=32, command=lambda: self._dock("left")).pack(side="left", padx=2)
        PremiumButton(header, text="▶", width=32, command=lambda: self._dock("right")).pack(side="left", padx=2)
        PremiumLabel(header, text="🚀 Elnagar Command Center", font=DS.get_font(14, "bold")).pack(side="left", padx=10)
        PremiumButton(header, text="✕", width=36, command=self.withdraw).pack(side="right", padx=10)
        
        self.tabs = ctk.CTkTabview(self, fg_color=DS.BG_CARD)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=5)
        OrdersTab(self.tabs.add("الطلبات"), self).pack(fill="both", expand=True)
        AddOrderTab(self.tabs.add("إضافة"), self).pack(fill="both", expand=True)
        CRMTab(self.tabs.add("العملاء"), self).pack(fill="both", expand=True)
        FilesTab(self.tabs.add("ملفات"), self).pack(fill="both", expand=True)
        NotesTab(self.tabs.add("ملاحظات"), self).pack(fill="both", expand=True)
        LaserOpsTab(self.tabs.add("ليزر"), self).pack(fill="both", expand=True)
        
        footer = ctk.CTkFrame(self, height=45, fg_color=DS.BG_CARD)
        footer.pack(fill="x", side="bottom")
        ctk.CTkSlider(footer, from_=0.5, to=1.0, command=lambda v: self.attributes('-alpha', v)).pack(side="left", padx=5)
        PremiumButton(footer, text="إغلاق", variant="secondary", command=sys.exit).pack(side="right", padx=5)
        self.withdraw()

    def _update_position(self):
        x = self.winfo_screenwidth() - self.width if self.docked_side == "right" else 0
        self.geometry(f"{self.width}x{self.winfo_screenheight()}+{x}+0")
    def _dock(self, side): self.docked_side = side; self._update_position()
    def _start_resize(self, event): self._resize_start_x = event.x_root; self._start_width = self.width
    def _do_resize(self, event):
        dx = event.x_root - self._resize_start_x
        self.width = max(300, min(self._start_width - dx if self.docked_side == "right" else self._start_width + dx, 800))
        self._update_position()

class App(ctk.CTk, TkinterDnD.DnDWrapper if dnd_avail else object):
    def __init__(self):
        super().__init__(); self.withdraw()
        self.sidebar = MainSidebar(self); self.icon = FloatingIcon(self, self._toggle)
        # Hide from taskbar
        self.after(100, lambda: hide_taskbar_icon(self))
        self.after(200, lambda: hide_taskbar_icon(self.icon))
        self.mainloop()
    def _toggle(self):
        self.sidebar.withdraw() if self.sidebar.state() == "normal" else self.sidebar.deiconify()

if __name__ == "__main__":
    try: app = App()
    except: pass
