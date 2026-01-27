from gui.main_window import TitanApp
from ttkthemes import ThemedTk

if __name__ == "__main__":
    # Aqui a gente define o tema "radiance" na criação da janela
    root = ThemedTk(theme="radiance")
    app = TitanApp(root)
    root.mainloop()