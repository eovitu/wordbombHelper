import tkinter as tk

class OverlayApp:
    def __init__(self, update_region_callback):
        self.update_callback_func = update_region_callback
        
        # Window Setup
        self.root = tk.Tk()
        self.root.title("WordBomb Helper Area")
        self.root.geometry("300x150+100+100")  # Default size and pos
        self.root.attributes('-topmost', True)  # Always on top
        # Make the background color (lime) completely transparent
        self.root.wm_attributes("-transparentcolor", "lime")
        self.root.configure(bg='lime')
        
        # Add a thick border frame so user can still see/drag it
        self.border_frame = tk.Frame(self.root, bg='red', bd=5)
        self.border_frame.pack(fill='both', expand=True)
        
        # Inner frame with transparent background
        self.inner_frame = tk.Frame(self.border_frame, bg='lime')
        self.inner_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # NO text label inside the overlay — it pollutes OCR readings!
        # The red border alone is enough for the user to see the area.
        
        # Start HIDDEN — only show when Auto-Play is activated
        self.root.withdraw()
        self._visible = False
        self._updating = False

    def start(self):
        self.root.mainloop()

    def show(self):
        """Show the overlay and start position updates."""
        if not self._visible:
            self.root.deiconify()
            self._visible = True
            if not self._updating:
                self._updating = True
                self.root.after(200, self.update_position)

    def hide(self):
        """Hide the overlay and stop position updates."""
        if self._visible:
            self.root.withdraw()
            self._visible = False
            self._updating = False

    def update_position(self):
        if not self._visible:
            self._updating = False
            return
            
        try:
            x = self.root.winfo_rootx()
            y = self.root.winfo_rooty()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            
            region = {
                'x1': x,
                'y1': y,
                'width': w,
                'height': h
            }
            if self.update_callback_func:
                self.update_callback_func(region)
        except Exception:
            pass
            
        self.root.after(200, self.update_position)

# Global reference so main.py can show/hide
_overlay_instance = None

def run_overlay(callback):
    global _overlay_instance
    _overlay_instance = OverlayApp(callback)
    _overlay_instance.start()

def get_overlay():
    return _overlay_instance
