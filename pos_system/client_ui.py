import customtkinter as ctk
from tkinter import messagebox, CENTER, RIGHT, LEFT
import database
import sys

# Setup Theme
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

class ManualBalanceDialog(ctk.CTkToplevel):
    def __init__(self, parent, current_balance, callback):
        super().__init__(parent)
        self.callback = callback
        self.title("تعديل الرصيد يدوياً")
        self.geometry("400x300")
        self.resizable(False, False)
        
        # Center Window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - 200
        y = (self.winfo_screenheight() // 2) - 150
        self.geometry(f"+{x}+{y}")
        
        self.attributes("-topmost", True)
        
        # Content
        self.label = ctk.CTkLabel(self, text="الرصيد الحالي للعامل", font=("Cairo", 14), text_color="gray")
        self.label.pack(pady=(20, 5))
        
        self.curr_lbl = ctk.CTkLabel(self, text=f"{current_balance:,.2f}", font=("Cairo", 24, "bold"), text_color="#2563EB")
        self.curr_lbl.pack(pady=5)
        
        self.input_label = ctk.CTkLabel(self, text="الرصيد الجديد المطلوب", font=("Cairo", 14, "bold"))
        self.input_label.pack(pady=(20, 5))
        
        self.entry = ctk.CTkEntry(self, placeholder_text="0.00", font=("Cairo", 16), justify="center", width=200)
        self.entry.pack(pady=10)
        self.entry.focus()
        
        self.save_btn = ctk.CTkButton(self, text="حفظ التعديل", font=("Cairo", 16, "bold"), fg_color="#EF4444", hover_color="#DC2626", command=self.save)
        self.save_btn.pack(pady=20)
        
    def save(self):
        val = self.entry.get()
        try:
            new_bal = float(val)
            self.callback(new_bal)
            self.destroy()
        except ValueError:
            messagebox.showerror("خطأ", "برجاء إدخال رقم صحيح")
            self.focus()

class StatCard(ctk.CTkFrame):
    def __init__(self, parent, title, value, color, text_color="white", command=None, **kwargs):
        super().__init__(parent, fg_color=color, corner_radius=15, **kwargs)
        self.command = command
        
        # Click event binding
        if command:
            self.bind("<Button-1>", self.on_click)
            self.configure(cursor="hand2")
            
        self.title_lbl = ctk.CTkLabel(self, text=title, font=("Cairo", 14, "bold"), text_color=text_color)
        self.title_lbl.pack(pady=(15, 5), padx=10)
        
        self.val_lbl = ctk.CTkLabel(self, text=value, font=("Cairo", 28, "bold"), text_color=text_color)
        self.val_lbl.pack(pady=(0, 15), padx=10)
        
        if command:
            self.title_lbl.bind("<Button-1>", self.on_click)
            self.val_lbl.bind("<Button-1>", self.on_click)
            
            # Edit Icon hint
            self.hint = ctk.CTkLabel(self, text="✏️ تعديل", font=("Cairo", 12), text_color=text_color)
            self.hint.pack(side="bottom", pady=5)
            self.hint.bind("<Button-1>", self.on_click)

    def on_click(self, event):
        if self.command:
            self.command()

class ClientDashboardApp(ctk.CTk):
    def __init__(self, client_id):
        super().__init__()
        self.client_id = client_id
        
        # Setup Window
        self.title("لوحة التحكم المالية للعميل")
        self.geometry("1000x600")
        
        # Grid Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) # Content area
        
        # 1. Header
        self.header = ctk.CTkFrame(self, fg_color="white", corner_radius=0, height=80)
        self.header.grid(row=0, column=0, sticky="ew")
        
        self.name_lbl = ctk.CTkLabel(self.header, text="تحميل...", font=("Cairo", 24, "bold"), text_color="#1E293B")
        self.name_lbl.place(relx=0.95, rely=0.5, anchor="e")
        
        self.phone_lbl = ctk.CTkLabel(self.header, text="", font=("Cairo", 16), text_color="#64748B")
        self.phone_lbl.place(relx=0.05, rely=0.5, anchor="w")
        
        # 2. Stats Container
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        self.stats_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="card")
        
        # Refresh Data
        self.refresh_data()
        
    def refresh_data(self):
        # Fetch Data
        data = database.get_client_financial_breakdown(self.client_id)
        
        # Fetch Basic Info (could be optimized into one call)
        conn = database.get_db_connection()
        client = conn.execute("SELECT name, phone FROM clients WHERE id=?", (self.client_id,)).fetchone()
        conn.close()
        
        # Update Header
        if client:
            self.name_lbl.configure(text=client['name'])
            self.phone_lbl.configure(text=client['phone'] or "لا يوجد هاتف")
            
        # Clear old cards
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
            
        # Format Currency
        def fmt(n):
            return f"{n:,.0f} ج.م"
            
        # Create Cards (RTL Order: Right is first column visually?? No, Grid logic: 0 is Left)
        # Arabic UI: Usually we want Start -> End (Right -> Left).
        # So Column 2 should be the "First" card visually (Processing), Column 0 "Last" (Total).
        # Or standard logical order. Let's place Total on Left (Red), Executed Middle, Processing Right.
        
        # Card 3: Total Net Debt (Red) - Column 0 (Left)
        # User requested: "Clicking this opens Manual Override".
        self.card_total = StatCard(self.stats_frame, 
                                   title="صافي المستحق (الرصيد)", 
                                   value=fmt(data['total_debt']), 
                                   color="#EF4444", 
                                   command=lambda: self.open_manual_override(data['total_debt']))
        self.card_total.grid(row=0, column=0, sticky="ew", padx=10)
        
        # Card 2: Executed Debt (Blue) - Column 1
        self.card_executed = StatCard(self.stats_frame, 
                                      title="مديونية تم التنفيذ (جاهز)", 
                                      value=fmt(data['executed_debt']), 
                                      color="#3B82F6")
        self.card_executed.grid(row=0, column=1, sticky="ew", padx=10)
        
        # Card 1: Processing Debt (Amber) - Column 2
        self.card_processing = StatCard(self.stats_frame, 
                                        title="مديونية جاري التجهيز", 
                                        value=fmt(data['processing_debt']), 
                                        color="#F59E0B")
        self.card_processing.grid(row=0, column=2, sticky="ew", padx=10)

    def open_manual_override(self, current_bal):
        ManualBalanceDialog(self, current_bal, self.perform_override)
        
    def perform_override(self, new_balance):
        res = database.adjust_balance(self.client_id, new_balance)
        if res['success']:
            messagebox.showinfo("تم بنجاح", "تم تعديل الرصيد وتسجيل الفرق في العمليات.")
            self.refresh_data()
        else:
            messagebox.showerror("خطأ", res.get('error', 'Unknown Error'))

if __name__ == "__main__":
    # Test with Client ID 1
    # Check if DB has client 1?
    try:
        app = ClientDashboardApp(1)
        app.mainloop()
    except Exception as e:
        print(f"Error launching app: {e}")
        # Keep window open to see error
        input("Press Enter to exit...")
