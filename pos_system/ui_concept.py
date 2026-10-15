import customtkinter as ctk
from tkinter import ttk

# --- Design Configuration ---
THEME_COLOR_BG = "#1A1A1A"        # Deep Charcoal
THEME_COLOR_SIDEBAR = "#141414"   # Darker Slate
THEME_COLOR_ACCENT = "#3B8ED0"    # Electric Blue (Default CTK blue is good, lets tweak)
THEME_COLOR_CARD = "#212121"      # Card Background
THEME_COLOR_TEXT_MAIN = "#FFFFFF"
THEME_COLOR_TEXT_SUB = "#A0A0A0"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue") 

class Smartsidebar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=THEME_COLOR_SIDEBAR, width=250, corner_radius=0, **kwargs)
        self.pack_propagate(False)
        
        # 1. Logo / Title Area
        self.logo_label = ctk.CTkLabel(
            self, 
            text="Elnagar POS", 
            font=("Roboto Medium", 22),
            text_color=THEME_COLOR_TEXT_MAIN
        )
        self.logo_label.pack(pady=30, padx=20, anchor="w")
        
        # 2. Navigation Items
        self.nav_buttons = []
        self.add_nav_item("Dashboard", active=True)
        self.add_nav_item("Orders")
        self.add_nav_item("Products")
        self.add_nav_item("Clients")
        self.add_nav_item("Suppliers")
        
        # 3. Footer / Settings
        self.settings_btn = ctk.CTkButton(
            self, 
            text="⚙  Settings", 
            fg_color="transparent", 
            text_color=THEME_COLOR_TEXT_SUB,
            hover_color="#2B2B2B",
            anchor="w"
        )
        self.settings_btn.pack(side="bottom", fill="x", padx=10, pady=20)

    def add_nav_item(self, text, active=False):
        # Visual styling for Active vs Inactive
        fg_color = THEME_COLOR_ACCENT if active else "transparent"
        text_color = "#FFFFFF" if active else THEME_COLOR_TEXT_SUB
        
        btn = ctk.CTkButton(
            self,
            text=f"  {text}",
            font=("Roboto", 14),
            fg_color=fg_color,
            text_color=text_color,
            hover_color="#2B2B2B",
            corner_radius=6,
            height=40,
            anchor="w"
        )
        btn.pack(pady=5, padx=10, fill="x")
        self.nav_buttons.append(btn)

class StatCard(ctk.CTkFrame):
    def __init__(self, master, label, value, trend, is_positive=True, **kwargs):
        super().__init__(master, fg_color=THEME_COLOR_CARD, corner_radius=12, **kwargs)
        
        # Inner Layout
        self.grid_columnconfigure(0, weight=1)
        
        # Top: Label + Icon Placeholder
        self.label_lbl = ctk.CTkLabel(
            self, 
            text=label.upper(), 
            font=("Roboto", 11, "bold"), 
            text_color=THEME_COLOR_TEXT_SUB
        )
        self.label_lbl.grid(row=0, column=0, sticky="w", padx=15, pady=(15,0))
        
        # Middle: Value
        self.value_lbl = ctk.CTkLabel(
            self, 
            text=value, 
            font=("Roboto", 28, "bold"), 
            text_color=THEME_COLOR_TEXT_MAIN
        )
        self.value_lbl.grid(row=1, column=0, sticky="w", padx=15, pady=(5,5))
        
        # Bottom: Trend
        color = "#00E676" if is_positive else "#FF5252" # Green/Red
        arrow = "▲" if is_positive else "▼"
        self.trend_lbl = ctk.CTkLabel(
            self, 
            text=f"{arrow} {trend} vs last month", 
            font=("Roboto", 11), 
            text_color=color
        )
        self.trend_lbl.grid(row=2, column=0, sticky="w", padx=15, pady=(0,15))

class MainContent(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=THEME_COLOR_BG, corner_radius=0, **kwargs)
        self.pack_propagate(False)
        
        # --- Header ---
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=30, pady=20)
        
        self.page_title = ctk.CTkLabel(
            self.header_frame, 
            text="Dashboard Overview", 
            font=("Roboto", 24, "bold"), 
            text_color=THEME_COLOR_TEXT_MAIN
        )
        self.page_title.pack(side="left")
        
        # Global Actions (Placeholders)
        action_btn_styles = {"width": 40, "height": 40, "fg_color": "#2B2B2B", "text_color": "#FFF"}
        ctk.CTkButton(self.header_frame, text="🔔", **action_btn_styles).pack(side="right", padx=5)
        ctk.CTkButton(self.header_frame, text="🔍", **action_btn_styles).pack(side="right", padx=5)
        
        # --- Stats Grid ---
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=25, pady=10)
        self.stats_frame.grid_columnconfigure((0,1,2,3), weight=1, uniform="stat")
        
        # Add Cards
        StatCard(self.stats_frame, "Total Revenue", "$124,500", "12%", True).grid(row=0, column=0, padx=5, sticky="ew")
        StatCard(self.stats_frame, "Total Orders", "1,240", "5%", True).grid(row=0, column=1, padx=5, sticky="ew")
        StatCard(self.stats_frame, "Pending", "45", "2%", False).grid(row=0, column=2, padx=5, sticky="ew")
        StatCard(self.stats_frame, "New Clients", "89", "18%", True).grid(row=0, column=3, padx=5, sticky="ew")

        # --- Recent Orders Table Section ---
        self.table_label = ctk.CTkLabel(self, text="Recent Transactions", font=("Roboto", 18, "bold"), text_color=THEME_COLOR_TEXT_MAIN)
        self.table_label.pack(anchor="w", padx=30, pady=(30, 10))
        
        self.table_frame = ctk.CTkFrame(self, fg_color=THEME_COLOR_CARD, corner_radius=10)
        self.table_frame.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        
        # Note: CustomTkinter doesn't have a native Table widget yet. 
        # We simulate one or use Treeview with dark styling. 
        # Here we simulate with grid for the "Prototype Look".
        
        # Header Row
        headers = ["ID", "Client", "Date", "Amount", "Status", "Action"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(
                self.table_frame, 
                text=h, 
                font=("Roboto", 12, "bold"), 
                text_color=THEME_COLOR_TEXT_SUB
            ).grid(row=0, column=i, sticky="w", padx=20, pady=15)
            
        # Mock Rows
        mock_data = [
            ("ORD-001", "Mahmoud Elnagar", "Today", "$120.00", "Completed"),
            ("ORD-002", "Smart Corp", "Yesterday", "$850.50", "Pending"),
            ("ORD-003", "Client X", "Oct 24", "$45.00", "Cancelled"),
        ]
        
        for idx, row_data in enumerate(mock_data):
            r = idx + 1
            ctk.CTkLabel(self.table_frame, text=row_data[0]).grid(row=r, column=0, sticky="w", padx=20, pady=10)
            ctk.CTkLabel(self.table_frame, text=row_data[1]).grid(row=r, column=1, sticky="w", padx=20, pady=10)
            ctk.CTkLabel(self.table_frame, text=row_data[2]).grid(row=r, column=2, sticky="w", padx=20, pady=10)
            ctk.CTkLabel(self.table_frame, text=row_data[3]).grid(row=r, column=3, sticky="w", padx=20, pady=10)
            
            # Status Badge Simulation
            status = row_data[4]
            badge_color = "#2CC985" if status == "Completed" else ("#FFB74D" if status == "Pending" else "#E53935")
            ctk.CTkButton(
                self.table_frame, 
                text=status, 
                fg_color=badge_color, 
                hover_color=badge_color,
                height=24, 
                width=80, 
                corner_radius=12,
                font=("Roboto", 10, "bold")
            ).grid(row=r, column=4, sticky="w", padx=20, pady=10)
            
            ctk.CTkButton(
                self.table_frame, 
                text="Edit", 
                fg_color="transparent", 
                border_width=1, 
                border_color="#555", 
                height=24, 
                width=60,
                text_color="#999"
            ).grid(row=r, column=5, sticky="w", padx=20, pady=10)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Elnagar POS - Modern UI Prototype")
        self.geometry("1100x700")
        
        # Layout: 2 Columns
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.sidebar = Smartsidebar(self)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.main_content = MainContent(self)
        self.main_content.grid(row=0, column=1, sticky="nsew")

if __name__ == "__main__":
    app = App()
    app.mainloop()
