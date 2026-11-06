import customtkinter as ctk
import sys
import os
import ctypes
import threading
import textwrap
from datetime import datetime
from core import (
    is_admin,
    load_config,
    get_ram_info,
    get_disk_free_gb,
    get_service_status,
    manage_service,
    is_tweak_applied,
    apply_tweak,
    restore_tweak,
    clean_temp_files,
    clean_shader_cache,
    clean_windows_update_cache,
    clean_crash_dumps,
    empty_recycle_bin,
    flush_dns_cache,
    reset_network_stack,
    create_restore_point,
    optimize_ram_workingset,
    open_system_tool,
)


class OptimizerApp(ctk.CTk):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.ui = self.config["ui"]
        self.services_cfg = self.config["services"]
        self.tweaks_cfg = self.config["tweaks"]
        self.articles_cfg = self.config["articles"]

        # Хранилище состояний UI
        self.service_vars = {}
        self.service_status_labels = {}
        self.tweak_vars = {}
        self.tweak_status_labels = {}
        self.stopped_in_session = []
        self.applied_tweaks_in_session = []
        self.tweak_rows = {}
        self.busy = False

        # Настройка главного окна
        ctk.set_appearance_mode(self.ui.get("appearance", "Dark"))
        self.configure(fg_color=self.ui["bg_color"])
        self.title("Advanced Windows & Game Optimizer Pro")
        self.geometry("1140x780")
        self.minsize(1000, 680)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()

        # Показываем стартовую вкладку и пишем приветствие в лог
        self.select_page("dashboard")
        self.log_action("Система готова к оптимизации. Права администратора подтверждены.", "info")
        self.refresh_all_statuses()
        self._schedule_ram_update()

    # ==================== БОКОВАЯ ПАНЕЛЬ ====================

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=self.ui["card_color"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Логотип / Заголовок
        title_lbl = ctk.CTkLabel(
            self.sidebar,
            text="⚡ WIN OPTIMIZER",
            font=("Segoe UI", 20, "bold"),
            text_color=self.ui["accent_color"],
        )
        title_lbl.pack(padx=20, pady=(24, 2), anchor="w")

        sub_lbl = ctk.CTkLabel(
            self.sidebar,
            text="Полный контроль и ускорение ОС",
            font=("Segoe UI", 12),
            text_color=self.ui["subtext_color"],
        )
        sub_lbl.pack(padx=20, pady=(0, 20), anchor="w")

        # Кнопки навигации
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "🚀  Центр оптимизации"),
            ("tweaks", "🛠  Системные твики"),
            ("services", "⚙  Службы Windows"),
            ("cleaner", "🧹  Очистка и ОЗУ"),
            ("articles", "📚  Статьи и Гайды"),
        ]

        for page_id, text in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=text,
                anchor="w",
                height=42,
                corner_radius=8,
                font=("Segoe UI", 14, "bold"),
                fg_color="transparent",
                text_color=self.ui["text_color"],
                hover_color=self.ui["secondary_color"],
                command=lambda p=page_id: self.select_page(p),
            )
            btn.pack(fill="x", padx=14, pady=4)
            self.nav_buttons[page_id] = btn

        # Карточка мониторинга ОЗУ внизу сайдбара
        self.ram_card = ctk.CTkFrame(self.sidebar, fg_color=self.ui["bg_color"], corner_radius=10)
        self.ram_card.pack(side="bottom", fill="x", padx=14, pady=18)

        ctk.CTkLabel(
            self.ram_card,
            text="Мониторинг памяти (ОЗУ)",
            font=("Segoe UI", 12, "bold"),
            text_color=self.ui["text_color"],
        ).pack(padx=12, pady=(10, 4), anchor="w")

        self.ram_bar = ctk.CTkProgressBar(
            self.ram_card,
            height=8,
            progress_color=self.ui["accent_color"],
            fg_color=self.ui["secondary_color"],
        )
        self.ram_bar.pack(fill="x", padx=12, pady=4)
        self.ram_bar.set(0.5)

        self.ram_label = ctk.CTkLabel(
            self.ram_card,
            text="Загрузка: --% (-- / -- ГБ)",
            font=("Consolas", 11),
            text_color=self.ui["subtext_color"],
        )
        self.ram_label.pack(padx=12, pady=(2, 8), anchor="w")

        ctk.CTkButton(
            self.ram_card,
            text="Освободить ОЗУ сейчас",
            height=28,
            font=("Segoe UI", 12, "bold"),
            fg_color=self.ui["secondary_color"],
            hover_color=self.ui["accent_color"],
            command=self.quick_clean_ram,
        ).pack(fill="x", padx=12, pady=(0, 10))

    # ==================== ОСНОВНАЯ ОБЛАСТЬ И ЖУРНАЛ ====================

    def _build_main_area(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=18)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=0)

        # Контейнер страниц
        self.pages_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.pages_frame.grid(row=0, column=0, sticky="nsew")
        self.pages_frame.grid_columnconfigure(0, weight=1)
        self.pages_frame.grid_rowconfigure(0, weight=1)

        self.pages = {}
        self._build_dashboard_page()
        self._build_tweaks_page()
        self._build_services_page()
        self._build_cleaner_page()
        self._build_articles_page()

        # Нижняя панель: Журнал того, что отключено / применено
        self.log_frame = ctk.CTkFrame(self.main_container, fg_color=self.ui["card_color"], corner_radius=12, height=185)
        self.log_frame.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        self.log_frame.grid_propagate(False)
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(1, weight=1)

        log_header = ctk.CTkFrame(self.log_frame, fg_color="transparent")
        log_header.grid(row=0, column=0, sticky="ew", padx=14, pady=(8, 4))

        ctk.CTkLabel(
            log_header,
            text="📋 Журнал действий (подробный отчёт: что отключено, изменено и очищено)",
            font=("Segoe UI", 13, "bold"),
            text_color=self.ui["text_color"],
        ).pack(side="left")

        ctk.CTkButton(
            log_header,
            text="Очистить лог",
            width=100,
            height=24,
            font=("Segoe UI", 11),
            fg_color=self.ui["secondary_color"],
            hover_color=self.ui["accent_hover"],
            command=self.clear_log,
        ).pack(side="right")

        ctk.CTkButton(
            log_header,
            text="💾 Сохранить лог",
            width=120,
            height=24,
            font=("Segoe UI", 11),
            fg_color=self.ui["secondary_color"],
            hover_color=self.ui["accent_hover"],
            command=self.save_log,
        ).pack(side="right", padx=(0, 6))

        self.log_box = ctk.CTkTextbox(
            self.log_frame,
            font=("Consolas", 12),
            fg_color=self.ui["bg_color"],
            text_color="#d8f3dc",
            corner_radius=8,
             state="disabled",
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 10))

    # ==================== СТРАНИЦА 1: ЦЕНТР ОПТИМИЗАЦИИ ====================

    def _build_dashboard_page(self):
        page = ctk.CTkFrame(self.pages_frame, fg_color="transparent")
        self.pages["dashboard"] = page

        # Заголовок
        ctk.CTkLabel(
            page,
            text="Центр быстрой оптимизации Windows",
            font=("Segoe UI", 24, "bold"),
            text_color=self.ui["text_color"],
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            page,
            text="Комплексное ускорение системы в 1 клик: отключение фоновых служб, применение игровых твиков реестра и очистка памяти.",
            font=("Segoe UI", 13),
            text_color=self.ui["subtext_color"],
        ).pack(anchor="w", pady=(0, 16))

        # Три карточки сводки
        cards_row = ctk.CTkFrame(page, fg_color="transparent")
        cards_row.pack(fill="x", pady=(0, 16))
        cards_row.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.stat_services_lbl = self._create_stat_card(
            cards_row, 0, "Фоновые службы", "Проверка...", "Остановлено ненужных служб"
        )
        self.stat_tweaks_lbl = self._create_stat_card(
            cards_row, 1, "Системные твики", "Проверка...", "Активно оптимизаций"
        )
        self.stat_ram_lbl = self._create_stat_card(
            cards_row, 2, "Свободно ОЗУ", "Проверка...", "Доступно физической памяти"
        )
        self.stat_disk_lbl = self._create_stat_card(
            cards_row, 3, "Системный диск", "Проверка...", "Свободно места на диске"
        )

        # Главная карточка управления "В 1 клик"
        hero = ctk.CTkFrame(page, fg_color=self.ui["card_color"], corner_radius=14)
        hero.pack(fill="both", expand=True)

        ctk.CTkLabel(
            hero,
            text="🔥 Профиль «Максимальная производительность и FPS»",
            font=("Segoe UI", 18, "bold"),
            text_color=self.ui["text_color"],
        ).pack(anchor="w", padx=22, pady=(18, 6))

        desc_text = (
            "При нажатии на кнопку «Оптимизировать Windows» программа выполнит все отмеченные галочками действия\n"
            "и выведет в журнал внизу полный список каждого отключённого компонента и изменённого параметра реестра:\n"
            "  • Остановит выбранные службы (SysMain, Windows Search, телеметрия, отчёты об ошибках, Spooler и др.)\n"
            "  • Применит выбранные твики: игры и FPS, сеть и пинг, система, приватность, интерфейс\n"
            "  • Очистит кэш DNS, временные файлы Temp и разгрузит оперативную память (Working Set)\n"
            "  🛡 Перед первой оптимизацией рекомендуется создать точку восстановления."
        )
        ctk.CTkLabel(
            hero,
            text=desc_text,
            justify="left",
            font=("Segoe UI", 13),
            text_color=self.ui["subtext_color"],
        ).pack(anchor="w", padx=22, pady=(0, 16))

        # Кнопки главного действия
        btn_row = ctk.CTkFrame(hero, fg_color="transparent")
        btn_row.pack(fill="x", padx=22, pady=(4, 18))

        self.btn_full_optimize = ctk.CTkButton(
            btn_row,
            text="⚡ ОПТИМИЗИРОВАТЬ WINDOWS (ВЫБРАННОЕ)",
            height=48,
            font=("Segoe UI", 15, "bold"),
            fg_color=self.ui["accent_color"],
            hover_color=self.ui["accent_hover"],
            corner_radius=10,
            command=self.run_full_optimization,
        )
        self.btn_full_optimize.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_full_restore = ctk.CTkButton(
            btn_row,
            text="↩ Восстановить стандартные настройки",
            height=48,
            font=("Segoe UI", 14, "bold"),
            fg_color=self.ui["secondary_color"],
            hover_color="#3d4459",
            corner_radius=10,
            command=self.run_full_restore,
        )
        self.btn_full_restore.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row,
            text="🔄 Обновить статусы",
            height=48,
            width=150,
            font=("Segoe UI", 13),
            fg_color=self.ui["bg_color"],
            hover_color=self.ui["secondary_color"],
            corner_radius=10,
            command=self.refresh_all_statuses,
        ).pack(side="right")

        btn_row2 = ctk.CTkFrame(hero, fg_color="transparent")
        btn_row2.pack(fill="x", padx=22, pady=(0, 18))

        self.btn_restore_point = ctk.CTkButton(
            btn_row2,
            text="🛡 Создать точку восстановления",
            height=38,
            font=("Segoe UI", 13, "bold"),
            fg_color=self.ui["secondary_color"],
            hover_color="#3d4459",
            corner_radius=10,
            command=self.action_restore_point,
        )
        self.btn_restore_point.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row2,
            text="🧹 Глубокая очистка (всё)",
            height=38,
            font=("Segoe UI", 13, "bold"),
            fg_color=self.ui["secondary_color"],
            hover_color="#3d4459",
            corner_radius=10,
            command=self.action_deep_clean,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row2,
            text="📚 Читать гайды",
            height=38,
            font=("Segoe UI", 13, "bold"),
            fg_color=self.ui["secondary_color"],
            hover_color="#3d4459",
            corner_radius=10,
            command=lambda: self.select_page("articles"),
        ).pack(side="left")

    def _create_stat_card(self, parent, col, title, big_value, subtitle):
        card = ctk.CTkFrame(parent, fg_color=self.ui["card_color"], corner_radius=12)
        card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0 if col == 3 else 6))

        ctk.CTkLabel(
            card, text=title, font=("Segoe UI", 13, "bold"), text_color=self.ui["subtext_color"]
        ).pack(anchor="w", padx=16, pady=(12, 2))

        val_lbl = ctk.CTkLabel(
            card, text=big_value, font=("Segoe UI", 22, "bold"), text_color=self.ui["success_color"]
        )
        val_lbl.pack(anchor="w", padx=16, pady=2)

        ctk.CTkLabel(
            card, text=subtitle, font=("Segoe UI", 11), text_color=self.ui["subtext_color"]
        ).pack(anchor="w", padx=16, pady=(0, 12))
        return val_lbl

    # ==================== СТРАНИЦА 2: СИСТЕМНЫЕ ТВИКИ ====================

    def _build_tweaks_page(self):
        page = ctk.CTkFrame(self.pages_frame, fg_color="transparent")
        self.pages["tweaks"] = page

        header = ctk.CTkFrame(page, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            header,
            text="Системные и игровые твики Windows",
            font=("Segoe UI", 22, "bold"),
            text_color=self.ui["text_color"],
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="Применить выбранные твики",
            fg_color=self.ui["accent_color"],
            hover_color=self.ui["accent_hover"],
            font=("Segoe UI", 13, "bold"),
            command=self.apply_selected_tweaks,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            header,
            text="Сбросить все твики",
            fg_color=self.ui["secondary_color"],
            hover_color="#3d4459",
            font=("Segoe UI", 13),
            command=self.restore_all_tweaks,
        ).pack(side="right")

        # Панель фильтра по категориям и быстрого выбора
        filter_bar = ctk.CTkFrame(page, fg_color="transparent")
        filter_bar.pack(fill="x", pady=(0, 8))

        categories = ["Все"]
        for tw in self.tweaks_cfg:
            if tw["category"] not in categories:
                categories.append(tw["category"])

        self.tweak_filter = ctk.CTkSegmentedButton(
            filter_bar,
            values=categories,
            font=("Segoe UI", 12, "bold"),
            selected_color=self.ui["accent_color"],
            selected_hover_color=self.ui["accent_hover"],
            unselected_color=self.ui["card_color"],
            command=self.filter_tweaks,
        )
        self.tweak_filter.set("Все")
        self.tweak_filter.pack(side="left")

        self._build_select_buttons(filter_bar, self.tweak_vars, self.tweaks_cfg, "id")

        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        self.tweaks_scroll = scroll

        for tw in self.tweaks_cfg:
            t_id = tw["id"]
            row = ctk.CTkFrame(scroll, fg_color=self.ui["card_color"], corner_radius=10)
            row.pack(fill="x", pady=5, padx=2)

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="both", expand=True, padx=14, pady=10)

            top_line = ctk.CTkFrame(left, fg_color="transparent")
            top_line.pack(fill="x")

            var = ctk.BooleanVar(value=tw.get("recommended", True))
            self.tweak_vars[t_id] = var

            cb = ctk.CTkCheckBox(
                top_line,
                text=tw["title"],
                variable=var,
                font=("Segoe UI", 14, "bold"),
                text_color=self.ui["text_color"],
                fg_color=self.ui["accent_color"],
                hover_color=self.ui["accent_hover"],
            )
            cb.pack(side="left")

            cat_badge = ctk.CTkLabel(
                top_line,
                text=f" {tw['category']} ",
                font=("Segoe UI", 11, "bold"),
                fg_color=self.ui["secondary_color"],
                text_color=self.ui["text_color"],
                corner_radius=6,
            )
            cat_badge.pack(side="left", padx=10)

            if tw.get("reboot"):
                ctk.CTkLabel(
                    top_line,
                    text=" ⟳ нужна перезагрузка ",
                    font=("Segoe UI", 11, "bold"),
                    fg_color="#3a2a12",
                    text_color=self.ui["warning_color"],
                    corner_radius=6,
                ).pack(side="left")

            if tw.get("recommended"):
                ctk.CTkLabel(
                    top_line,
                    text=" ★ рекомендуется ",
                    font=("Segoe UI", 11, "bold"),
                    fg_color="#12332f",
                    text_color=self.ui["success_color"],
                    corner_radius=6,
                ).pack(side="left", padx=(6, 0))

            self.tweak_rows[t_id] = (row, tw["category"])

            ctk.CTkLabel(
                left,
                text=tw["description"],
                font=("Segoe UI", 12),
                text_color=self.ui["subtext_color"],
                justify="left",
                wraplength=560,
            ).pack(anchor="w", pady=(4, 0))

            right = ctk.CTkFrame(row, fg_color="transparent")
            right.pack(side="right", padx=14, pady=10)

            status_lbl = ctk.CTkLabel(
                right,
                text="Проверка...",
                font=("Consolas", 12, "bold"),
                width=110,
            )
            status_lbl.pack(side="left", padx=(0, 10))
            self.tweak_status_labels[t_id] = status_lbl

            ctk.CTkButton(
                right,
                text="Вкл",
                width=56,
                height=30,
                fg_color=self.ui["accent_color"],
                hover_color=self.ui["accent_hover"],
                command=lambda tid=t_id, title=tw["title"]: self.single_tweak_action(tid, title, True),
            ).pack(side="left", padx=3)

            ctk.CTkButton(
                right,
                text="Сброс",
                width=64,
                height=30,
                fg_color=self.ui["secondary_color"],
                hover_color="#3d4459",
                command=lambda tid=t_id, title=tw["title"]: self.single_tweak_action(tid, title, False),
            ).pack(side="left", padx=3)

    # ==================== СТРАНИЦА 3: СЛУЖБЫ WINDOWS ====================

    def _build_services_page(self):
        page = ctk.CTkFrame(self.pages_frame, fg_color="transparent")
        self.pages["services"] = page

        header = ctk.CTkFrame(page, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            header,
            text="Управление фоновыми службами Windows",
            font=("Segoe UI", 22, "bold"),
            text_color=self.ui["text_color"],
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="Остановить выбранные",
            fg_color=self.ui["accent_color"],
            hover_color=self.ui["accent_hover"],
            font=("Segoe UI", 13, "bold"),
            command=self.stop_selected_services,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            header,
            text="Запустить выбранные",
            fg_color=self.ui["secondary_color"],
            hover_color="#3d4459",
            font=("Segoe UI", 13),
            command=self.start_selected_services,
        ).pack(side="right")

        info_bar = ctk.CTkFrame(page, fg_color="transparent")
        info_bar.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            info_bar,
            text="ℹ Службы останавливаются только до перезагрузки — тип запуска не меняется, это безопасно.",
            font=("Segoe UI", 12),
            text_color=self.ui["subtext_color"],
        ).pack(side="left")
        self._build_select_buttons(info_bar, self.service_vars, self.services_cfg, "name")

        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        for srv in self.services_cfg:
            s_name = srv["name"]
            row = ctk.CTkFrame(scroll, fg_color=self.ui["card_color"], corner_radius=10)
            row.pack(fill="x", pady=5, padx=2)

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="both", expand=True, padx=14, pady=10)

            var = ctk.BooleanVar(value=srv.get("recommended", True))
            self.service_vars[s_name] = var

            cb = ctk.CTkCheckBox(
                left,
                text=f"{srv['title']}  [{s_name}]",
                variable=var,
                font=("Segoe UI", 14, "bold"),
                text_color=self.ui["text_color"],
                fg_color=self.ui["accent_color"],
                hover_color=self.ui["accent_hover"],
            )
            cb.pack(anchor="w")

            ctk.CTkLabel(
                left,
                text=srv["description"],
                font=("Segoe UI", 12),
                text_color=self.ui["subtext_color"],
                justify="left",
            ).pack(anchor="w", pady=(4, 0))

            right = ctk.CTkFrame(row, fg_color="transparent")
            right.pack(side="right", padx=14, pady=10)

            st_lbl = ctk.CTkLabel(right, text="...", font=("Consolas", 12, "bold"), width=115)
            st_lbl.pack(side="left", padx=(0, 10))
            self.service_status_labels[s_name] = st_lbl

            ctk.CTkButton(
                right,
                text="Стоп",
                width=60,
                height=30,
                fg_color=self.ui["accent_color"],
                hover_color=self.ui["accent_hover"],
                command=lambda n=s_name, t=srv["title"]: self.single_service_action(n, t, "stop"),
            ).pack(side="left", padx=3)

            ctk.CTkButton(
                right,
                text="Старт",
                width=60,
                height=30,
                fg_color=self.ui["secondary_color"],
                hover_color="#3d4459",
                command=lambda n=s_name, t=srv["title"]: self.single_service_action(n, t, "start"),
            ).pack(side="left", padx=3)

    # ==================== СТРАНИЦА 4: ОЧИСТКА И ОЗУ ====================

    def _build_cleaner_page(self):
        page = ctk.CTkFrame(self.pages_frame, fg_color="transparent")
        self.pages["cleaner"] = page

        ctk.CTkLabel(
            page,
            text="Очистка мусора, кэша и освобождение ОЗУ",
            font=("Segoe UI", 22, "bold"),
            text_color=self.ui["text_color"],
        ).pack(anchor="w", pady=(0, 12))

        grid = ctk.CTkScrollableFrame(page, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure((0, 1), weight=1)

        cards = [
            ("🧠 Оптимизация оперативной памяти",
             "Выгружает неиспользуемые страницы памяти фоновых приложений (WinAPI EmptyWorkingSet) перед запуском игры.",
             "Разгрузить ОЗУ сейчас", self.quick_clean_ram, True),
            ("🗑 Временные файлы (Temp)",
             "Удаляет мусор из %TEMP% и C:\\Windows\\Temp. Prefetch не трогаем — это кэш ускорения запуска программ.",
             "Очистить временные файлы", self.action_clean_temp, True),
            ("🎮 Кэш шейдеров DirectX / NVIDIA / AMD",
             "Помогает при статтерах и артефактах после обновления драйвера. Первый запуск игр после очистки будет чуть дольше.",
             "Очистить кэш шейдеров", self.action_clean_shaders, False),
            ("🔄 Кэш обновлений Windows",
             "Удаляет уже установленные/скачанные файлы обновлений из SoftwareDistribution\\Download. Может освободить гигабайты.",
             "Очистить кэш обновлений", self.action_clean_wu, False),
            ("💥 Дампы сбоев и отчёты об ошибках",
             "Удаляет Minidump, LiveKernelReports, CrashDumps и архив отчётов WER, которые копятся после вылетов.",
             "Удалить дампы и отчёты", self.action_clean_dumps, False),
            ("♻ Корзина",
             "Окончательно очищает корзину на всех дисках без лишних подтверждений.",
             "Очистить корзину", self.action_empty_bin, False),
            ("🌐 Сброс кэша DNS (Flush DNS)",
             "Очищает устаревшие записи DNS-резолвера, устраняя проблемы подключения к серверам и сайтам.",
             "Очистить DNS-кэш", self.action_flush_dns, False),
            ("🛠 Сброс сетевого стека (Winsock / TCP-IP)",
             "Лечит обрывы интернета, «Нет подключения» и аномальный пинг после VPN и сетевых программ. Нужна перезагрузка.",
             "Сбросить сеть", self.action_reset_network, False),
        ]

        for i, (title, desc, btn_text, cmd, accent) in enumerate(cards):
            r, c = divmod(i, 2)
            card = ctk.CTkFrame(grid, fg_color=self.ui["card_color"], corner_radius=12)
            card.grid(row=r, column=c, sticky="nsew", padx=(0, 6) if c == 0 else (6, 0), pady=6)
            ctk.CTkLabel(card, text=title, font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
            ctk.CTkLabel(
                card,
                text=desc,
                font=("Segoe UI", 12),
                text_color=self.ui["subtext_color"],
                wraplength=360,
                justify="left",
            ).pack(anchor="w", padx=16, pady=(0, 12))
            ctk.CTkButton(
                card,
                text=btn_text,
                fg_color=self.ui["accent_color"] if accent else self.ui["secondary_color"],
                hover_color=self.ui["accent_hover"] if accent else self.ui["accent_color"],
                font=("Segoe UI", 13, "bold"),
                command=cmd,
            ).pack(anchor="w", padx=16, pady=(0, 14))

        # Быстрые системные утилиты Windows
        tools_card = ctk.CTkFrame(grid, fg_color=self.ui["card_color"], corner_radius=12)
        tools_card.grid(row=len(cards) // 2 + 1, column=0, columnspan=2, sticky="nsew", pady=6)
        ctk.CTkLabel(tools_card, text="🔧 Быстрый доступ к утилитам Windows", font=("Segoe UI", 15, "bold")).pack(
            anchor="w", padx=16, pady=(14, 6)
        )

        tools_wrap = ctk.CTkFrame(tools_card, fg_color="transparent")
        tools_wrap.pack(fill="x", padx=16, pady=(0, 14))
        tools_wrap.grid_columnconfigure((0, 1, 2), weight=1)

        quick_tools = [
            ("Автозагрузка приложений", "ms-settings:startupapps"),
            ("Настройки графики (HAGS)", "ms-settings:display-advancedgraphics"),
            ("Игровой режим Windows", "ms-settings:gaming-gamemode"),
            ("Очистка диска (cleanmgr)", "cleanmgr"),
            ("Контроль памяти (Storage Sense)", "ms-settings:storagesense"),
            ("Оптимизация дисков", "dfrgui"),
            ("Диспетчер задач", "taskmgr"),
            ("Монитор ресурсов", "resmon"),
            ("Схемы электропитания", "powercfg.cpl"),
            ("Параметры быстродействия", "SystemPropertiesPerformance"),
            ("Планировщик заданий", "taskschd.msc"),
            ("Службы Windows", "services.msc"),
            ("Просмотр событий", "eventvwr.msc"),
            ("Безопасность Windows", "windowsdefender:"),
            ("Восстановление системы", "rstrui"),
        ]
        for i, (label, cmd) in enumerate(quick_tools):
            r, c = divmod(i, 3)
            ctk.CTkButton(
                tools_wrap,
                text=f"↗ {label}",
                anchor="w",
                height=30,
                fg_color=self.ui["secondary_color"],
                hover_color="#3d4459",
                font=("Segoe UI", 12),
                command=lambda c_=cmd, l=label: self.launch_tool(c_, l),
            ).grid(row=r, column=c, sticky="ew", padx=3, pady=3)

    # ==================== СТРАНИЦА 5: СТАТЬИ И ГАЙДЫ ====================

    def _build_articles_page(self):
        page = ctk.CTkFrame(self.pages_frame, fg_color="transparent")
        self.pages["articles"] = page
        page.grid_columnconfigure(1, weight=1)
        page.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            page,
            text="📚 База знаний и статьи: как правильно оптимизировать Windows",
            font=("Segoe UI", 21, "bold"),
            text_color=self.ui["text_color"],
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        # Список статей слева: поиск + прокручиваемый список
        articles_side = ctk.CTkFrame(page, width=310, fg_color=self.ui["card_color"], corner_radius=12)
        articles_side.grid(row=1, column=0, sticky="ns", padx=(0, 12))
        articles_side.grid_propagate(False)
        articles_side.grid_columnconfigure(0, weight=1)
        articles_side.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            articles_side,
            text=f"Статей в базе: {len(self.articles_cfg)}",
            font=("Segoe UI", 13, "bold"),
            text_color=self.ui["subtext_color"],
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))

        self.article_search = ctk.CTkEntry(
            articles_side,
            placeholder_text="🔍 Поиск по статьям (например: пинг, SSD)",
            fg_color=self.ui["bg_color"],
            border_color=self.ui["secondary_color"],
        )
        self.article_search.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        self.article_search.bind("<KeyRelease>", lambda e: self.filter_articles())

        articles_list = ctk.CTkScrollableFrame(articles_side, fg_color="transparent")
        articles_list.grid(row=2, column=0, sticky="nsew", padx=2, pady=(0, 8))

        self.article_buttons = {}
        for idx, art in enumerate(self.articles_cfg):
            btn = ctk.CTkButton(
                articles_list,
                text=f"[{art['tag']}]\n" + textwrap.fill(art["title"], 30),
                anchor="w",
                height=52,
                corner_radius=8,
                font=("Segoe UI", 12, "bold"),
                fg_color="transparent",
                text_color=self.ui["text_color"],
                hover_color=self.ui["secondary_color"],
                command=lambda i=idx: self.show_article(i),
            )
            btn.pack(fill="x", padx=4, pady=3)
            self.article_buttons[idx] = btn

        # Панель чтения статьи справа
        reader_card = ctk.CTkFrame(page, fg_color=self.ui["card_color"], corner_radius=12)
        reader_card.grid(row=1, column=1, sticky="nsew")
        reader_card.grid_columnconfigure(0, weight=1)
        reader_card.grid_rowconfigure(1, weight=1)

        reader_header = ctk.CTkFrame(reader_card, fg_color="transparent")
        reader_header.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))

        self.article_title_lbl = ctk.CTkLabel(
            reader_header,
            text="",
            font=("Segoe UI", 17, "bold"),
            text_color=self.ui["accent_color"],
        )
        self.article_title_lbl.pack(side="left")

        self.article_action_btn = ctk.CTkButton(
            reader_header,
            text="Открыть раздел Windows",
            height=30,
            fg_color=self.ui["secondary_color"],
            hover_color=self.ui["accent_color"],
            font=("Segoe UI", 12, "bold"),
        )
        self.article_action_btn.pack(side="right")

        self.article_textbox = ctk.CTkTextbox(
            reader_card,
            font=("Segoe UI", 13),
            fg_color=self.ui["bg_color"],
            text_color=self.ui["text_color"],
            wrap="word",
            corner_radius=8,
            state="disabled",
        )
        self.article_textbox.grid(row=1, column=0, sticky="nsew", padx=18, pady=(4, 16))

        if self.articles_cfg:
            self.show_article(0)

    def show_article(self, idx):
        art = self.articles_cfg[idx]
        for i, btn in self.article_buttons.items():
            btn.configure(fg_color=self.ui["secondary_color"] if i == idx else "transparent")

        self.article_title_lbl.configure(text=art["title"])
        cmd = art.get("action_cmd", "")
        label = art.get("action_label", "Открыть настройку")
        self.article_action_btn.configure(
            text=f"↗ {label}",
            command=lambda c=cmd, l=label: self.launch_tool(c, l),
        )

        self.article_textbox.configure(state="normal")
        self.article_textbox.delete("1.0", "end")
        self.article_textbox.insert("1.0", art["content"])
        self.article_textbox.configure(state="disabled")

    # ==================== ЛОГИКА НАВИГАЦИИ И ЖУРНАЛА ====================

    def select_page(self, page_id):
        for pid, frame in self.pages.items():
            if pid == page_id:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()

        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.configure(fg_color=self.ui["accent_color"], text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", text_color=self.ui["text_color"])

    def log_action(self, message, level="ok"):
        now = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "ok": "✔ [ВЫПОЛНЕНО]",
            "restore": "↩ [ВОССТАНОВЛЕНО]",
            "warn": "⚠ [ВНИМАНИЕ]",
            "info": "ℹ [ИНФО]",
        }.get(level, "•")

        line = f"[{now}] {prefix} {message}\n"
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.log_action("Журнал очищен.", "info")

    # ==================== ОБНОВЛЕНИЕ СТАТУСОВ ====================

    def refresh_all_statuses(self):
        stopped_count = 0
        for srv in self.services_cfg:
            name = srv["name"]
            st = get_service_status(name)
            lbl = self.service_status_labels.get(name)
            if st == "STOPPED":
                stopped_count += 1
                if lbl:
                    lbl.configure(text="● ОСТАНОВЛЕНА", text_color=self.ui["success_color"])
            elif st == "RUNNING":
                if lbl:
                    lbl.configure(text="● РАБОТАЕТ", text_color=self.ui["warning_color"])
            else:
                if lbl:
                    lbl.configure(text="○ НЕ НАЙДЕНА", text_color=self.ui["subtext_color"])

        active_tweaks = 0
        for tw in self.tweaks_cfg:
            tid = tw["id"]
            applied = is_tweak_applied(tid)
            lbl = self.tweak_status_labels.get(tid)
            if applied:
                active_tweaks += 1
                if lbl:
                    lbl.configure(text="✔ АКТИВЕН", text_color=self.ui["success_color"])
            else:
                if lbl:
                    lbl.configure(text="○ СТАНДАРТ", text_color=self.ui["subtext_color"])

        ram = get_ram_info()
        self.stat_services_lbl.configure(text=f"{stopped_count} из {len(self.services_cfg)}")
        self.stat_tweaks_lbl.configure(text=f"{active_tweaks} из {len(self.tweaks_cfg)}")
        self.stat_ram_lbl.configure(text=f"{ram['avail_gb']} ГБ ({100 - ram['load_percent']}%)")
        free_gb, total_gb = get_disk_free_gb()
        self.stat_disk_lbl.configure(
            text=f"{free_gb} / {total_gb} ГБ",
            text_color=self.ui["success_color"] if total_gb == 0 or free_gb / total_gb > 0.15 else self.ui["warning_color"],
        )

    def _schedule_ram_update(self):
        ram = get_ram_info()
        self.ram_bar.set(ram["load_percent"] / 100.0)
        self.ram_label.configure(
            text=f"Занято: {ram['load_percent']}% ({ram['used_gb']} / {ram['total_gb']} ГБ)"
        )
        self.stat_ram_lbl.configure(text=f"{ram['avail_gb']} ГБ ({100 - ram['load_percent']}%)")
        self.after(3000, self._schedule_ram_update)

    # ==================== ОБРАБОТЧИКИ ДЕЙСТВИЙ ====================

    def single_service_action(self, service_name, title, action):
        ok, msg = manage_service(service_name, action)
        if ok:
            if action == "stop":
                if service_name not in self.stopped_in_session:
                    self.stopped_in_session.append(service_name)
                self.log_action(f"Отключена служба: {title} ({service_name})", "ok")
            else:
                self.log_action(f"Запущена служба: {title} ({service_name})", "restore")
        else:
            self.log_action(msg, "warn")
        self.refresh_all_statuses()

    def stop_selected_services(self):
        count = 0
        for srv in self.services_cfg:
            name = srv["name"]
            if self.service_vars[name].get():
                ok, msg = manage_service(name, "stop")
                if ok:
                    count += 1
                    if name not in self.stopped_in_session:
                        self.stopped_in_session.append(name)
                    self.log_action(f"Отключена служба: {srv['title']} [{name}] — {srv['description']}", "ok")
                else:
                    self.log_action(msg, "warn")
                self.update_idletasks()
        self.log_action(f"Итог по службам: остановлено {count} выбранных служб.", "info")
        self.refresh_all_statuses()

    def start_selected_services(self):
        count = 0
        for srv in self.services_cfg:
            name = srv["name"]
            if self.service_vars[name].get():
                ok, msg = manage_service(name, "start")
                if ok:
                    count += 1
                    self.log_action(f"Включена обратно служба: {srv['title']} [{name}]", "restore")
                else:
                    self.log_action(msg, "warn")
                self.update_idletasks()
        self.log_action(f"Итог: запущено {count} служб.", "info")
        self.refresh_all_statuses()

    def single_tweak_action(self, tweak_id, title, enable=True):
        if enable:
            ok, msg = apply_tweak(tweak_id)
            if ok:
                if tweak_id not in self.applied_tweaks_in_session:
                    self.applied_tweaks_in_session.append(tweak_id)
                self.log_action(f"Твик применён [{title}]: {msg}", "ok")
            else:
                self.log_action(msg, "warn")
        else:
            ok, msg = restore_tweak(tweak_id)
            if ok:
                self.log_action(f"Твик сброшен [{title}]: {msg}", "restore")
            else:
                self.log_action(msg, "warn")
        self.refresh_all_statuses()

    def apply_selected_tweaks(self):
        count = 0
        need_reboot = []
        for tw in self.tweaks_cfg:
            tid = tw["id"]
            if self.tweak_vars[tid].get():
                ok, msg = apply_tweak(tid)
                if ok:
                    count += 1
                    if tid not in self.applied_tweaks_in_session:
                        self.applied_tweaks_in_session.append(tid)
                    self.log_action(f"Применён твик «{tw['title']}»: {msg}", "ok")
                    if tw.get("reboot"):
                        need_reboot.append(tw["title"])
                else:
                    self.log_action(msg, "warn")
                self.update_idletasks()
        self.log_action(f"Успешно применено системных твиков: {count}", "info")
        if need_reboot:
            self.log_action(
                f"Для вступления в силу {len(need_reboot)} твиков нужна перезагрузка ПК: " + ", ".join(need_reboot),
                "warn",
            )
        self.refresh_all_statuses()

    def restore_all_tweaks(self):
        count = 0
        for tw in self.tweaks_cfg:
            tid = tw["id"]
            ok, msg = restore_tweak(tid)
            if ok:
                count += 1
                self.log_action(f"Восстановлен стандартный параметр «{tw['title']}»: {msg}", "restore")
            self.update_idletasks()
        self.log_action(f"Все системные твики ({count}) возвращены к значениям по умолчанию Windows.", "info")
        self.refresh_all_statuses()

    def quick_clean_ram(self):
        procs, freed_mb = optimize_ram_workingset()
        self.log_action(
            f"Очистка ОЗУ завершена: оптимизировано {procs} процессов, освобождено ~{freed_mb} МБ памяти.",
            "ok",
        )
        self.refresh_all_statuses()

    def action_clean_temp(self):
        files_cnt, freed_mb = clean_temp_files()
        self.log_action(
            f"Очистка Temp: удалено объектов: {files_cnt}, освобождено места: {freed_mb} МБ.",
            "ok",
        )

    def action_flush_dns(self):
        if flush_dns_cache():
            self.log_action("Кэш DNS успешно очищен (ipconfig /flushdns).", "ok")
        else:
            self.log_action("Не удалось очистить DNS-кэш.", "warn")

    def launch_tool(self, cmd, label):
        if open_system_tool(cmd):
            self.log_action(f"Открыта системная утилита: {label} ({cmd})", "info")
        else:
            self.log_action(f"Не удалось открыть: {label}", "warn")

    # ==================== ФОНОВЫЕ ЗАДАЧИ (без зависания окна) ====================

    def run_bg(self, title, func, on_done):
        """Запускает долгую операцию в отдельном потоке, результат обрабатывается в потоке UI."""
        if self.busy:
            self.log_action("Дождитесь завершения текущей операции...", "warn")
            return
        self.busy = True
        self.log_action(f"{title}... (окно не зависло, операция выполняется в фоне)", "info")
        box = {}

        def worker():
            try:
                box["result"] = func()
            except Exception as e:
                box["error"] = e

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        def poll():
            if t.is_alive():
                self.after(200, poll)
                return
            self.busy = False
            if "error" in box:
                self.log_action(f"{title}: ошибка — {box['error']}", "warn")
            else:
                on_done(box["result"])
            self.refresh_all_statuses()

        self.after(200, poll)

    def _log_clean_result(self, name, result):
        cnt, mb = result
        self.log_action(f"{name}: удалено объектов: {cnt}, освобождено: {mb} МБ.", "ok")

    def action_clean_shaders(self):
        self.run_bg("Очистка кэша шейдеров", clean_shader_cache,
                    lambda r: self._log_clean_result("Кэш шейдеров DirectX/NVIDIA/AMD очищен", r))

    def action_clean_wu(self):
        self.run_bg("Очистка кэша обновлений Windows", clean_windows_update_cache,
                    lambda r: self._log_clean_result("Кэш обновлений (SoftwareDistribution\\Download) очищен", r))

    def action_clean_dumps(self):
        self.run_bg("Удаление дампов сбоев и отчётов WER", clean_crash_dumps,
                    lambda r: self._log_clean_result("Дампы сбоев и отчёты об ошибках удалены", r))

    def action_empty_bin(self):
        if empty_recycle_bin():
            self.log_action("Корзина очищена на всех дисках.", "ok")
        else:
            self.log_action("Не удалось очистить корзину.", "warn")
        self.refresh_all_statuses()

    def action_reset_network(self):
        def done(res):
            ws, ip = res
            self.log_action(f"Сброс Winsock: {'успешно' if ws else 'ошибка'}; сброс TCP/IP: {'успешно' if ip else 'ошибка'}.",
                            "ok" if ws and ip else "warn")
            self.log_action("Перезагрузите компьютер, чтобы сброс сети вступил в силу.", "warn")
        self.run_bg("Сброс сетевого стека", reset_network_stack, done)

    def action_restore_point(self):
        def done(res):
            ok, msg = res
            self.log_action(msg, "ok" if ok else "warn")
        self.run_bg("Создание точки восстановления системы (до 1–2 минут)", create_restore_point, done)

    def action_deep_clean(self):
        def job():
            results = [
                ("Temp", clean_temp_files()),
                ("Кэш шейдеров", clean_shader_cache()),
                ("Кэш обновлений Windows", clean_windows_update_cache()),
                ("Дампы сбоев и WER", clean_crash_dumps()),
            ]
            bin_ok = empty_recycle_bin()
            dns_ok = flush_dns_cache()
            return results, bin_ok, dns_ok

        def done(res):
            results, bin_ok, dns_ok = res
            total = 0.0
            for name, (cnt, mb) in results:
                total += mb
                self.log_action(f"Глубокая очистка — {name}: удалено {cnt} объектов, {mb} МБ.", "ok")
            self.log_action("Корзина очищена." if bin_ok else "Корзину очистить не удалось.", "ok" if bin_ok else "warn")
            self.log_action("Кэш DNS очищен." if dns_ok else "Кэш DNS очистить не удалось.", "ok" if dns_ok else "warn")
            self.log_action(f"=== ГЛУБОКАЯ ОЧИСТКА ЗАВЕРШЕНА: освобождено ~{round(total, 1)} МБ (без учёта корзины) ===", "info")

        self.run_bg("Глубокая очистка системы", job, done)

    # ==================== ВЫБОР, ФИЛЬТРЫ, ЛОГ ====================

    def _build_select_buttons(self, parent, vars_dict, items, key):
        def set_all(mode):
            for it in items:
                v = vars_dict.get(it[key])
                if v is None:
                    continue
                if mode == "all":
                    v.set(True)
                elif mode == "none":
                    v.set(False)
                else:
                    v.set(bool(it.get("recommended")))

        for text, mode in (("Снять все", "none"), ("Выбрать все", "all"), ("★ Рекомендуемые", "rec")):
            ctk.CTkButton(
                parent,
                text=text,
                width=110,
                height=28,
                font=("Segoe UI", 12),
                fg_color=self.ui["card_color"],
                hover_color=self.ui["secondary_color"],
                command=lambda m=mode: set_all(m),
            ).pack(side="right", padx=(6, 0))

    def filter_tweaks(self, category):
        for row, _cat in self.tweak_rows.values():
            row.pack_forget()
        for tw in self.tweaks_cfg:
            row, cat = self.tweak_rows[tw["id"]]
            if category == "Все" or cat == category:
                row.pack(fill="x", pady=5, padx=2)

    def filter_articles(self):
        query = self.article_search.get().strip().lower()
        for idx, btn in self.article_buttons.items():
            btn.pack_forget()
        for idx, art in enumerate(self.articles_cfg):
            text = (art["title"] + " " + art["tag"] + " " + art["content"]).lower()
            if not query or query in text:
                self.article_buttons[idx].pack(fill="x", padx=4, pady=3)

    def save_log(self):
        folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"optimizer_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_box.get("1.0", "end"))
            self.log_action(f"Журнал сохранён в файл: {path}", "info")
        except Exception as e:
            self.log_action(f"Не удалось сохранить журнал: {e}", "warn")

    # ==================== ПОЛНАЯ ОПТИМИЗАЦИЯ И ВОССТАНОВЛЕНИЕ ====================

    def run_full_optimization(self):
        self.log_action("=== ЗАПУСК ПОЛНОЙ ОПТИМИЗАЦИИ WINDOWS ===", "info")
        self.update_idletasks()

        # 1. Останавливаем отмеченные службы
        self.stop_selected_services()

        # 2. Применяем отмеченные твики реестра и питания
        self.apply_selected_tweaks()

        # 3. Очищаем DNS, Temp и разгружаем ОЗУ
        self.action_flush_dns()
        self.action_clean_temp()
        self.quick_clean_ram()

        self.log_action("=== ПОЛНАЯ ОПТИМИЗАЦИЯ УСПЕШНО ЗАВЕРШЕНА! СИСТЕМА ГОТОВА К ИГРЕ ===", "info")

    def run_full_restore(self):
        self.log_action("=== ЗАПУСК ВОССТАНОВЛЕНИЯ СТАНДАРТНЫХ ПАРАМЕТРОВ WINDOWS ===", "info")
        self.update_idletasks()

        # Восстанавливаем все твики
        self.restore_all_tweaks()

        # Запускаем службы, остановленные в этом сеансе (или выбранные, если таких нет)
        if self.stopped_in_session:
            for name in list(self.stopped_in_session):
                title = next((s["title"] for s in self.services_cfg if s["name"] == name), name)
                ok, msg = manage_service(name, "start")
                self.log_action(f"Включена обратно служба: {title} [{name}]" if ok else msg, "restore" if ok else "warn")
                self.update_idletasks()
            self.stopped_in_session.clear()
            self.refresh_all_statuses()
        else:
            self.start_selected_services()

        self.log_action("=== ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО ===", "info")


if __name__ == "__main__":
    if is_admin():
        cfg = load_config()
        app = OptimizerApp(cfg)
        app.mainloop()
    else:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 1
        )
