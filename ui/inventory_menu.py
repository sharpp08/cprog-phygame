"""Pause-on-open survival inventory overlay."""
from __future__ import annotations

import pygame

from ui.widgets import FontSet, text


class InventoryMenu:
    """Inventory view backed by the game's existing weapon/survival systems."""

    def __init__(self, width: int, height: int) -> None:
        self.W, self.H = width, height
        self.fonts = FontSet()
        self.selected = 0
        self.message = "SELECT AN ITEM TO INSPECT"
        self._slots = []

    def _items(self, player, survival, story):
        items = []
        for index, weapon in enumerate(player.weapons):
            items.append({
                "kind": "weapon", "index": index,
                "name": weapon.name.upper(),
                "count": f"{weapon.mag} / {weapon.reserve} AMMO",
                "detail": f"{weapon.name}  |  {weapon.fire_mode.upper()}  |  MAGAZINE {weapon.mag}/{weapon.mag_size}",
                "action": "EQUIP" if index != player.current else "EQUIPPED",
            })
        if survival is not None:
            supplies = [
                ("medkit", "FIELD MEDKIT", survival.medkits, "Restores 40 health when used.", "USE"),
                ("grenade", "FRAGMENTATION GRENADE", survival.grenades, "A throwable explosive. Use G while aiming.", "READY"),
                ("battery", "FLASHLIGHT CELL", survival.battery_cells, "Replace a depleted flashlight battery.", "INSTALL"),
                ("scrap", "SCAVENGED SCRAP", survival.scrap, "Materials recovered from defeated enemies.", "MATERIAL"),
            ]
            for kind, name, amount, detail, action in supplies:
                items.append({"kind": kind, "name": name, "count": f"x {amount}",
                              "detail": detail, "action": action})
            items.append({
                "kind": "flashlight", "name": "FLASHLIGHT",
                "count": f"{int(survival.flashlight_battery)}%  |  {'ON' if survival.flashlight_on else 'OFF'}",
                "detail": "A dwindling light source. Press F to toggle it.",
                "action": "STATUS",
            })
        if story is not None:
            found = len(story.discovered)
            total = len(story.clues)
            items.append({
                "kind": "key", "name": "FIELD NOTES",
                "count": f"{found} / {total} CLUES",
                "detail": "Evidence and fragments collected during the investigation.",
                "action": "INSPECT",
            })
        return items

    def _perform(self, item, player, survival, audio):
        kind = item["kind"]
        if kind == "weapon":
            player.select_weapon(item["index"])
            self.message = f"{item['name']} EQUIPPED"
            audio.play("weapon_switch")
        elif kind == "medkit" and survival is not None:
            if survival.use_medkit(player):
                self.message = "FIELD DRESSING APPLIED  |  +40 HP"
                audio.play("medkit_use")
            else:
                self.message = "NO MEDKITS AVAILABLE OR HEALTH IS FULL"
        elif kind == "battery" and survival is not None:
            if survival.replace_battery():
                player.flashlight_on = survival.flashlight_on
                self.message = "FRESH CELL INSTALLED"
                audio.play("battery_swap")
            else:
                self.message = "NO SPARE CELL OR BATTERY IS ALREADY FULL"
        elif kind == "grenade":
            self.message = "PRESS G DURING GAMEPLAY TO THROW A GRENADE"
        elif kind == "key":
            self.message = "FIELD NOTES ARE STORED IN YOUR JOURNAL"
        else:
            self.message = item["detail"]
        audio.play("item_select")

    def handle(self, event, player, survival, story, audio):
        items = self._items(player, survival, story)
        if items:
            self.selected = max(0, min(self.selected, len(items) - 1))
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_i, pygame.K_TAB):
                audio.play("inventory_close")
                return "close"
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % max(1, len(items))
                audio.play("item_select")
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % max(1, len(items))
                audio.play("item_select")
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and items:
                self._perform(items[self.selected], player, survival, audio)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, rect in enumerate(self._slots):
                if rect.collidepoint(event.pos):
                    self.selected = index
                    audio.play("item_select")
                    return None
            if getattr(self, "_action_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) and items:
                self._perform(items[self.selected], player, survival, audio)
            elif getattr(self, "_close_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                audio.play("inventory_close")
                return "close"
        return None

    def draw(self, screen, player, survival, story):
        items = self._items(player, survival, story)
        overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        overlay.fill((2, 5, 6, 218))
        screen.blit(overlay, (0, 0))

        panel_w = min(900, self.W - 48)
        panel_h = min(610, self.H - 42)
        panel = pygame.Rect((self.W - panel_w) // 2, (self.H - panel_h) // 2,
                            panel_w, panel_h)
        pygame.draw.rect(screen, (9, 16, 15), panel, border_radius=10)
        pygame.draw.rect(screen, (91, 111, 91), panel, 1, border_radius=10)
        text(screen, self.fonts, "FIELD INVENTORY", panel.x + 30, panel.y + 38,
             32, (226, 216, 184), "left", True)
        text(screen, self.fonts, "SCAVENGED SUPPLIES  /  EQUIPMENT  /  EVIDENCE",
             panel.x + 32, panel.y + 68, 14, (132, 153, 135), "left")
        pygame.draw.line(screen, (78, 91, 76), (panel.x + 26, panel.y + 88),
                         (panel.right - 26, panel.y + 88), 1)

        list_rect = pygame.Rect(panel.x + 26, panel.y + 108,
                                int(panel_w * 0.53), panel_h - 190)
        row_h = min(54, max(42, (list_rect.height - 4) // max(1, min(8, len(items)))))
        self._slots = []
        for i, item in enumerate(items):
            y = list_rect.y + i * row_h
            if y + row_h > list_rect.bottom:
                break
            rect = pygame.Rect(list_rect.x, y, list_rect.width, row_h - 5)
            self._slots.append(rect)
            selected = i == self.selected
            bg = (49, 61, 51) if selected else (20, 30, 27)
            pygame.draw.rect(screen, bg, rect, border_radius=5)
            if selected:
                pygame.draw.rect(screen, (174, 145, 91), rect, 1, border_radius=5)
            color = (235, 226, 197) if selected else (175, 185, 166)
            text(screen, self.fonts, item["name"], rect.x + 12, rect.y + 16,
                 17, color, "left", True)
            text(screen, self.fonts, item["count"], rect.right - 10,
                 rect.y + 16, 15, (190, 170, 125), "right")

        detail_x = list_rect.right + 28
        detail_w = panel.right - 28 - detail_x
        detail = pygame.Rect(detail_x, list_rect.y, detail_w, list_rect.height)
        pygame.draw.rect(screen, (14, 23, 20), detail, border_radius=6)
        pygame.draw.rect(screen, (57, 75, 62), detail, 1, border_radius=6)
        if items:
            item = items[self.selected]
            text(screen, self.fonts, item["name"], detail.x + 18,
                 detail.y + 34, 22, (224, 212, 177), "left", True)
            text(screen, item.get("fonts", self.fonts), item["count"],
                 detail.x + 18, detail.y + 66, 16, (185, 164, 121), "left")
            lines = item["detail"].split(" ")
            wrapped, line = [], ""
            for word in lines:
                test = (line + " " + word).strip()
                if len(test) > 29:
                    wrapped.append(line)
                    line = word
                else:
                    line = test
            if line:
                wrapped.append(line)
            for i, part in enumerate(wrapped[:5]):
                text(screen, self.fonts, part, detail.x + 18,
                     detail.y + 110 + i * 23, 15, (158, 174, 158), "left")
            text(screen, self.fonts, f"STATUS: {item['action']}",
                 detail.x + 18, detail.bottom - 30, 14,
                 (194, 177, 132), "left", True)

        self._action_rect = pygame.Rect(panel.x + 26, panel.bottom - 62, 190, 38)
        self._close_rect = pygame.Rect(panel.right - 176, panel.bottom - 62, 150, 38)
        for rect, label, fill in ((self._action_rect, "USE / EQUIP", (62, 77, 61)),
                                  (self._close_rect, "CLOSE  [ESC]", (40, 51, 47))):
            pygame.draw.rect(screen, fill, rect, border_radius=5)
            pygame.draw.rect(screen, (111, 126, 98), rect, 1, border_radius=5)
            text(screen, self.fonts, label, rect.centerx, rect.centery,
                 15, (231, 224, 199), "center", True)
        text(screen, self.fonts, self.message, panel.centerx, panel.bottom - 82,
             13, (145, 161, 139), "center")
        text(screen, self.fonts, "UP / DOWN SELECT  •  ENTER ACTION  •  ESC CLOSE",
             panel.centerx, panel.bottom - 12, 12, (104, 121, 106), "center")
