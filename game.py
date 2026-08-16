import random
import sys
import tkinter as tk
from tkinter import messagebox
import requests

from cards import WikiDeckGame

if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1) # 1 = Process_System_DPI_Aware
    except Exception:
        pass

# ------------------------------------------------------------
# Wikipedia: choose two random popular articles
# ------------------------------------------------------------

PAGEVIEWS_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
    "en.wikipedia/all-access/{year}/{month:02d}/all-days"
)

NON_ARTICLE_PREFIXES = {
    "Wikipedia", "Help", "File", "Category", "Talk", "Special",
    "Portal", "Template", "User", "Draft", "Module", "MediaWiki",
    "Book", "Image",
}


def get_popular_articles(count=2):
    """Get random articles from the most-viewed English Wikipedia pages
    over the past 2 completed months.

    Each month's top-100 list is fetched and merged into one pool, so the
    game draws from a wider, more varied set than a single day or month
    would give -- while still favoring genuinely popular articles.

    Note: this starts from *last* month, not the current one -- Wikimedia
    doesn't publish a month's aggregate until that month has closed, so
    the in-progress current month would just 404.

    Falls back to a small curated list if the API is unavailable or
    returns too few usable titles.
    """
    from datetime import date

    MONTHS_BACK = 2

    combined_titles = []
    seen = set()

    year, month = date.today().year, date.today().month

    # Step back to last month first -- see docstring note above.
    month -= 1
    if month == 0:
        month = 12
        year -= 1

    for _ in range(MONTHS_BACK):
        url = PAGEVIEWS_URL.format(year=year, month=month)

        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Wiki Card Game"},
                timeout=15,
            )
            response.raise_for_status()

            items = response.json().get("items") or []
            articles = items[0].get("articles", []) if items else []

        except Exception:
            articles = []

        for article in articles:
            title = article.get("article", "").replace("_", " ").strip()

            if not title:
                continue

            if ":" in title and title.split(":", 1)[0] in NON_ARTICLE_PREFIXES:
                continue

            # Avoid special Wikimedia entries and obvious list pages.
            if title.lower().startswith(("main page", "special:", "list of ")):
                continue

            if title not in seen:
                combined_titles.append(title)
                seen.add(title)

        # Step back one month, rolling the year over as needed.
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    if len(combined_titles) >= count:
        return random.sample(combined_titles, count)

    # Final fallback so the UI still works offline.
    FALLBACK = [
        "Python (programming language)",
        "Philosophy",
        "Science",
        "Game",
        "History",
        "Art",
        "Mathematics",
        "Music",
    ]

    return random.sample(FALLBACK, count)


# ------------------------------------------------------------
# Soft, cute color palette
# ------------------------------------------------------------

BG = "#FFF7FB"
PANEL = "#FFEAF3"
PINK = "#F6A6C1"
PINK_DARK = "#D96F98"
YELLOW = "#FFF1B8"
BLUE = "#DDF2FF"
BLUE_DARK = "#8FC9EC"
CARD_BG = "#FFFFFF"
CARD_BORDER = "#F2C6D7"
TEXT = "#4B3B45"
MUTED = "#8A7480"
WHITE = "#FFFFFF"


# ------------------------------------------------------------
# GUI
# ------------------------------------------------------------

class WikiCardGameApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Wiki Card Game ♡")
        self.root.geometry("1050x760")
        self.root.minsize(850, 650)
        self.root.configure(bg=BG)

        self.font = "Ubuntu"
        self.bold_font = (self.font, 20, "bold")
        self.small_font = (self.font, 15)
        self.card_font = (self.font, 18, "bold")
        self.title_font = (self.font, 30, "bold")

        self.game = None
        self.target_title = None
        self.loading = False

        # Discard-selection state: when discard_mode is True, clicking a
        # card toggles its membership in selected_for_discard instead of
        # playing it.
        self.discard_mode = False
        self.selected_for_discard = set()

        self.build_layout()
        self.new_game()

    # -------------------------
    # Layout
    # -------------------------

    def build_layout(self):

        # Simple, spacious layout:
        # title -> route -> cards -> actions.

        main = tk.Frame(self.root, bg=BG)
        main.pack(
            fill="both",
            expand=True,
            padx=42,
            pady=18
        )

        tk.Label(
            main,
            text="Find your way from one Wikipedia article to another!",
            bg=BG,
            fg=PINK_DARK,
            font=self.title_font
        ).pack(pady=20)

        # -------------------------
        # Start / Target
        # -------------------------

        route = tk.Frame(main, bg=BG)
        route.pack(fill="x", pady=(0, 16))

        route.columnconfigure(0, weight=1)
        route.columnconfigure(2, weight=1)

        self.start_label = tk.Label(
            route,
            text="START\n—",
            bg=PINK,
            fg=TEXT,
            font=self.bold_font,

            #Same fixed dimensions as TARGET
            width=32,
            height=2,

            padx=24,
            pady=14,
            justify="center"
        )

        self.start_label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 10)
        )

        tk.Label(
            route,
            text="→",
            bg=BG,
            fg=PINK_DARK,
            font=(self.font, 24, "bold")
        ).grid(
            row=0,
            column=1,
            padx=4
        )

        self.target_label = tk.Label(
            route,
            text="TARGET\n—",
            bg=PINK,
            fg=TEXT,
            font=self.bold_font,

            # Same fixed dimensions as START
            width=32,
            height=2,

            padx=24,
            pady=14,
            justify="center"
        )

        self.target_label.grid(
            row=0,
            column=2,
            sticky="ew",
            padx=(10, 0)
        )

        # -------------------------
        # Status
        # -------------------------

        self.status_label = tk.Label(
            main,
            text="Loading...",
            bg=BG,
            fg=MUTED,
            font=self.small_font
        )

        self.status_label.pack(pady=(0, 12))

        # -------------------------
        # Cards heading
        # -------------------------

        cards_header = tk.Frame(main, bg=BG)
        cards_header.pack(fill="x", pady=(0, 8))

        tk.Label(
            cards_header,
            text="YOUR CARDS",
            bg=BG,
            fg=TEXT,
            font=(self.font, 17, "bold")
        ).pack(side="left")

        self.count_label = tk.Label(
            cards_header,
            text="",
            bg=BG,
            fg=MUTED,
            font=self.small_font
        )

        self.count_label.pack(side="right")

        # -------------------------
        # Card area
        # -------------------------

        outer = tk.Frame(main, bg=BG)
        outer.pack(fill="both", expand=True)

        self.card_canvas = tk.Canvas(
            outer,
            bg=BG,
            highlightthickness=0,
            bd=0
        )

        scrollbar = tk.Scrollbar(
            outer,
            orient="vertical",
            command=self.card_canvas.yview,
            troughcolor=BG,
            bg=PINK,
            activebackground=PINK_DARK,
            relief="flat",
            bd=0,
            width=10
        )

        self.card_canvas.configure(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side="right",
            fill="y",
            padx=(8, 0)
        )

        self.card_canvas.pack(
            side="left",
            fill="both",
            expand=True
        )

        self.card_frame = tk.Frame(
            self.card_canvas,
            bg=BG
        )

        self.card_window = self.card_canvas.create_window(
            (0, 0),
            window=self.card_frame,
            anchor="nw"
        )

        self.card_frame.bind(
            "<Configure>",
            lambda event: self.card_canvas.configure(
                scrollregion=self.card_canvas.bbox("all")
            )
        )

        self.card_canvas.bind(
            "<Configure>",
            self.resize_card_frame
        )

        self.bind_mousewheel_scrolling()

        # -------------------------
        # Actions
        # -------------------------

        actions = tk.Frame(main, bg=BG)
        actions.pack(fill="x", pady=(14, 0))

        self.discard_button = tk.Button(
            actions,
            text="Select cards to discard",
            command=self.toggle_discard_mode,
            bg=BLUE,
            fg=TEXT,
            activebackground="#C8E9FB",
            activeforeground=TEXT,
            font=self.bold_font,
            relief="flat",
            bd=0,
            padx=20,
            pady=9,
            cursor="hand2"
        )

        self.discard_button.pack(side="left")

        self.confirm_discard_button = tk.Button(
            actions,
            text="Discard selected (0)",
            command=self.confirm_discard,
            bg=PINK,
            fg=TEXT,
            activebackground=PINK_DARK,
            activeforeground=WHITE,
            font=self.bold_font,
            relief="flat",
            bd=0,
            padx=20,
            pady=9,
            cursor="hand2",
            state="disabled"
        )
        # Only shown once discard mode is active; see enter_discard_mode.

        self.new_game_button = tk.Button(
            actions,
            text="New game",
            command=self.new_game,
            bg=YELLOW,
            fg=TEXT,
            activebackground="#FFE99A",
            activeforeground=TEXT,
            font=self.bold_font,
            relief="flat",
            bd=0,
            padx=24,
            pady=9,
            cursor="hand2"
        )

        self.new_game_button.pack(side="right")

    def resize_card_frame(self, event):
        self.card_canvas.itemconfigure(
            self.card_window,
            width=event.width
        )

    def bind_mousewheel_scrolling(self):
        """Let the card list scroll with the mouse wheel / trackpad, not
        just by dragging the scrollbar.

        Bound globally (bind_all) rather than only on the canvas, because
        the cards are separate child widgets layered on top of the canvas
        -- an <Enter>/<Leave> binding on the canvas alone would stop
        working as soon as the pointer crossed onto a card. Since this
        window has only one scrollable area, a global binding is safe.
        """

        def on_mousewheel(event):
            # Windows / macOS send <MouseWheel> with a signed event.delta.
            # Linux (X11) sends <Button-4> (up) / <Button-5> (down) instead.
            if event.num == 4:
                self.card_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.card_canvas.yview_scroll(1, "units")
            elif event.delta:
                direction = -1 if event.delta > 0 else 1
                self.card_canvas.yview_scroll(direction, "units")

        self.root.bind_all("<MouseWheel>", on_mousewheel)
        self.root.bind_all("<Button-4>", on_mousewheel)
        self.root.bind_all("<Button-5>", on_mousewheel)

    # -------------------------
    # Game setup
    # -------------------------

    def new_game(self):

        if self.loading:
            return

        if self.discard_mode:
            self.exit_discard_mode()

        self.loading = True

        self.new_game_button.configure(
            state="disabled"
        )

        self.discard_button.configure(
            state="disabled"
        )

        self.status_label.configure(
            text="Finding two popular Wikipedia articles..."
        )

        self.root.update_idletasks()

        try:
            start_title, target_title = get_popular_articles(2)

            self.game = WikiDeckGame(
                start_title,
                target_title
            )

            self.target_title = target_title

            self.start_label.configure(
                text=f"START\n{start_title}"
            )

            self.target_label.configure(
                text=f"TARGET\n{target_title}"
            )

            self.status_label.configure(
                text="Choose a card to play. Reach the target article to win!"
            )

            self.refresh_cards()

        except Exception as exc:

            self.status_label.configure(
                text="Couldn't reach Wikipedia."
            )

            messagebox.showerror(
                "Wikipedia Error",
                f"I couldn't get the popular articles from Wikipedia.\n\n{exc}",
            )

        finally:

            self.loading = False

            self.new_game_button.configure(
                state="normal"
            )

            self.discard_button.configure(
                state="normal"
            )

    # -------------------------
    # Cards
    # -------------------------

    def refresh_cards(self):

        for widget in self.card_frame.winfo_children():
            widget.destroy()

        if not self.game:
            return

        cards = self.game.current_cards

        self.count_label.configure(
            text=f"{len(cards)} card(s)"
        )

        if not cards:

            tk.Label(
                self.card_frame,
                text="Your deck is empty! ♡",
                bg=BG,
                fg=TEXT,
                font=self.bold_font,
                pady=50
            ).pack(fill="x")

            return

        columns = 3

        for column in range(columns):
            self.card_frame.columnconfigure(
                column,
                weight=1
            )

        for index, card_title in enumerate(cards):

            row = index // columns
            column = index % columns

            self.make_card(
                card_title,
                row,
                column,
                selected=card_title in self.selected_for_discard
            )

    def make_card(self, title, row, column, selected=False):

        base_bg = PANEL if selected else CARD_BG
        base_border = PINK_DARK if selected else CARD_BORDER

        card = tk.Frame(
            self.card_frame,
            bg=base_bg,
            highlightbackground=base_border,
            highlightthickness=3 if selected else 2,
            bd=0,
            width=280,
            height=90
        )

        card.grid(
            row=row,
            column=column,
            padx=8,
            pady=8,
            sticky="nsew"
        )

        # Keep the frame at the fixed size above instead of shrinking
        # or growing to fit the title label's content.
        card.grid_propagate(False)
        card.pack_propagate(False)

        display_text = f"✓ {title}" if selected else title

        title_label = tk.Label(
            card,
            text=display_text,
            bg=base_bg,
            fg=PINK_DARK if selected else TEXT,
            font=self.card_font,
            justify="center",
            padx=16,
            pady=10
        )

        title_label.pack(
            fill="both",
            expand=True
        )

        def on_enter(event):
            card.configure(bg=PANEL)
            title_label.configure(bg=PANEL)

        def on_leave(event):
            card.configure(bg=base_bg)
            title_label.configure(bg=base_bg)

        for widget in (card, title_label):

            widget.bind(
                "<Enter>",
                on_enter
            )

            widget.bind(
                "<Leave>",
                on_leave
            )

            widget.bind(
                "<Button-1>",
                lambda event, t=title: self.on_card_click(t)
            )

    # -------------------------
    # Game actions
    # -------------------------

    def on_card_click(self, title):
        """Route a card click to either playing it or toggling its
        discard-selection, depending on the current mode."""

        if not self.game or self.loading:
            return

        if self.discard_mode:
            self.toggle_card_selection(title)
        else:
            self.play_card(title)

    def play_card(self, title):

        try:
            result = self.game.choose_card(title)

        except Exception as exc:

            messagebox.showerror(
                "Card Error",
                str(exc)
            )

            return

        if result["won"]:

            self.refresh_cards()

            self.status_label.configure(
                text=f"♡ YOU FOUND {self.target_title.upper()}! ♡"
            )

            self.show_win_dialog(self.target_title)

            return

        linked = result.get("linked_cards", [])
        added = result.get("added_cards", [])

        if not linked:

            self.status_label.configure(
                text=f"You played {title}. "
                     "No qualifying links were found, so your deck is unchanged."
            )

        elif added:

            self.status_label.configure(
                text=f"You played {title}. "
                     f"{len(added)} new card(s) appeared!"
            )

        else:

            self.status_label.configure(
                text=f"You played {title}. "
                     "Every linked article was already in your deck, "
                     "so no new cards were added."
            )

        self.refresh_cards()

        if not self.game.current_cards:

            self.status_label.configure(
                text="Your deck is empty — you lose! Start a new game."
            )

            messagebox.showinfo(
                "Game Over",
                "You ran out of cards!\n\nTry another game.",
            )

    def show_win_dialog(self, target_title):
        """A custom win popup, since tkinter's messagebox has a fixed
        size/font that can't be enlarged."""

        dialog = tk.Toplevel(self.root)
        dialog.title("Wiki Card Game ♡")
        dialog.configure(bg=BG)

        # This is the actual "size" control -- messagebox has no equivalent.
        dialog.geometry("520x360")
        dialog.minsize(520, 360)

        dialog.transient(self.root)
        dialog.grab_set()  # modal, like messagebox

        tk.Label(
            dialog,
            text="You Win! ♡",
            bg=BG,
            fg=PINK_DARK,
            font=(self.font, 30, "bold")
        ).pack(pady=(36, 12))

        tk.Label(
            dialog,
            text=f"You reached:\n\n{target_title}\n\nCongratulations!",
            bg=BG,
            fg=TEXT,
            font=(self.font, 18),
            justify="center"
        ).pack(pady=12, padx=24)

        tk.Button(
            dialog,
            text="Nice!",
            command=dialog.destroy,
            bg=PINK,
            fg=TEXT,
            activebackground=PINK_DARK,
            activeforeground=WHITE,
            font=self.bold_font,
            relief="flat",
            bd=0,
            padx=24,
            pady=8,
            cursor="hand2"
        ).pack(pady=20)

        # Center the dialog over the main window.
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

    # -------------------------
    # Discard mode
    # -------------------------

    def toggle_discard_mode(self):

        if not self.game or self.loading:
            return

        if self.discard_mode:
            self.exit_discard_mode()
        else:
            self.enter_discard_mode()

    def enter_discard_mode(self):

        if not self.game.current_cards:
            return

        self.discard_mode = True
        self.selected_for_discard = set()

        self.discard_button.configure(
            text="Cancel",
            bg=PANEL
        )

        self.confirm_discard_button.configure(
            text="Discard selected (0)",
            state="disabled"
        )

        self.confirm_discard_button.pack(
            side="left",
            padx=(10, 0)
        )

        self.new_game_button.configure(
            state="disabled"
        )

        self.status_label.configure(
            text="Tap cards to select them, then confirm. "
                 "Every 5 cards you discard earns 1 replacement card."
        )

        self.refresh_cards()

    def exit_discard_mode(self):

        self.discard_mode = False
        self.selected_for_discard = set()

        self.discard_button.configure(
            text="Select cards to discard",
            bg=BLUE
        )

        self.confirm_discard_button.pack_forget()

        self.new_game_button.configure(
            state="normal"
        )

        self.refresh_cards()

    def toggle_card_selection(self, title):

        if title in self.selected_for_discard:
            self.selected_for_discard.remove(title)
        else:
            self.selected_for_discard.add(title)

        count = len(self.selected_for_discard)

        self.confirm_discard_button.configure(
            text=f"Discard selected ({count})",
            state="normal" if count else "disabled"
        )

        self.refresh_cards()

    def confirm_discard(self):

        if not self.game or not self.selected_for_discard:
            return

        titles = list(self.selected_for_discard)

        try:
            discarded, replacements = self.game.discard_cards(titles)

        except Exception as exc:

            messagebox.showerror(
                "Discard Error",
                str(exc)
            )

            return

        discarded_text = ", ".join(discarded)

        if replacements:

            replacements_text = ", ".join(replacements)

            self.status_label.configure(
                text=f"Discarded {len(discarded)} card(s): {discarded_text}. "
                     f"Gained {len(replacements)} new card(s): {replacements_text}."
            )

        else:

            self.status_label.configure(
                text=f"Discarded {len(discarded)} card(s): {discarded_text}. "
                     "Discard 5 or more at once to earn a replacement card."
            )

        self.exit_discard_mode()

        if not self.game.current_cards:

            self.status_label.configure(
                text="Your deck is empty — you lose! Start a new game."
            )

            messagebox.showinfo(
                "Game Over",
                "You discarded your last card and ran out of cards!\n\nTry another game.",
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = WikiCardGameApp(root)
    root.mainloop()
