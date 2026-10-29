# ui.py - User Interface for menus, HUD, and buttons

import pygame
from settings import *

class Button:
    def __init__(self, x, y, width, height, text, font, base_color=(60, 60, 70), hover_color=(90, 90, 110), text_color=WHITE):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.base_color = base_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.is_hovered = False

    def draw(self, surface):
        color = self.hover_color if self.is_hovered else self.base_color
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        pygame.draw.rect(surface, (150, 150, 160), self.rect, 2, border_radius=6)
        
        txt_surf = self.font.render(self.text, True, self.text_color)
        txt_rect = txt_surf.get_rect(center=self.rect.center)
        surface.blit(txt_surf, txt_rect)

    def check_hover(self, mouse_pos):
        self.is_hovered = self.rect.collidepoint(mouse_pos)
        return self.is_hovered

    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False

class UI:
    def __init__(self, screen):
        self.screen = screen
        self.title_font = pygame.font.SysFont("arial", 56, bold=True)
        self.header_font = pygame.font.SysFont("arial", 36, bold=True)
        self.font = pygame.font.SysFont("arial", 22)
        self.small_font = pygame.font.SysFont("arial", 18)

    def draw_hud(self, score, wave, health, max_health, zombies_left, announcement=""):
        # Health bar
        bar_x = 30
        bar_y = 30
        bar_w = 220
        bar_h = 24
        
        pct = max(0, min(1.0, health / max_health))
        fill_w = int(bar_w * pct)
        
        pygame.draw.rect(self.screen, DARK_GRAY, (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4), border_radius=4)
        health_color = GREEN if pct > 0.4 else (YELLOW if pct > 0.2 else RED)
        if fill_w > 0:
            pygame.draw.rect(self.screen, health_color, (bar_x, bar_y, fill_w, bar_h), border_radius=3)
            
        health_txt = self.small_font.render(f"HP: {int(health)}/{max_health}", True, WHITE)
        self.screen.blit(health_txt, (bar_x + 10, bar_y + 2))
        
        # Wave & Score info
        wave_txt = self.header_font.render(f"WAVE: {wave}", True, WHITE)
        score_txt = self.header_font.render(f"SCORE: {score}", True, YELLOW)
        zombies_txt = self.font.render(f"Zombies Remaining: {zombies_left}", True, (220, 220, 220))
        
        self.screen.blit(wave_txt, (SCREEN_WIDTH - 220, 25))
        self.screen.blit(score_txt, (SCREEN_WIDTH - 220, 65))
        self.screen.blit(zombies_txt, (SCREEN_WIDTH - 250, 105))
        
        # Announcement banner
        if announcement:
            banner_surf = self.header_font.render(announcement, True, RED)
            banner_rect = banner_surf.get_rect(center=(SCREEN_WIDTH // 2, 80))
            bg_rect = banner_rect.inflate(40, 16)
            s = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            s.fill((0, 0, 0, 180))
            self.screen.blit(s, bg_rect)
            self.screen.blit(banner_surf, banner_rect)

    def draw_pause_menu(self, buttons):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        
        title_surf = self.title_font.render("GAME PAUSED", True, WHITE)
        title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3 - 30))
        self.screen.blit(title_surf, title_rect)
        
        for btn in buttons:
            btn.draw(self.screen)

    def draw_game_over(self, final_score, high_score, wave_reached, buttons):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((40, 10, 10, 210))
        self.screen.blit(overlay, (0, 0))
        
        title_surf = self.title_font.render("GAME OVER", True, RED)
        title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, 140))
        self.screen.blit(title_surf, title_rect)
        
        score_surf = self.header_font.render(f"Final Score: {final_score}", True, WHITE)
        score_rect = score_surf.get_rect(center=(SCREEN_WIDTH // 2, 220))
        self.screen.blit(score_surf, score_rect)
        
        high_surf = self.font.render(f"High Score: {high_score}", True, YELLOW)
        high_rect = high_surf.get_rect(center=(SCREEN_WIDTH // 2, 265))
        self.screen.blit(high_surf, high_rect)
        
        wave_surf = self.font.render(f"Survived up to Wave {wave_reached}", True, (200, 200, 200))
        wave_rect = wave_surf.get_rect(center=(SCREEN_WIDTH // 2, 300))
        self.screen.blit(wave_surf, wave_rect)
        
        for btn in buttons:
            btn.draw(self.screen)
