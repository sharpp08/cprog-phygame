# main.py - Application entry point for Zombie Survival: Last Stand

import sys
import importlib

try:
    pygame = importlib.import_module("pygame")
except ModuleNotFoundError as e:
    if e.name == "pygame":
        print("Pygame is required. Install it with: python -m pip install pygame", file=sys.stderr)
        sys.exit(1)
    raise

from settings import SCREEN_WIDTH, SCREEN_HEIGHT, TITLE, FPS
from game import Game

def main():
    try:
        pygame.init()
    except Exception as e:
        print(f"Error initializing Pygame: {e}", file=sys.stderr)
        sys.exit(1)

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(TITLE)

    # Set icon
    icon_surf = pygame.Surface((32, 32))
    icon_surf.fill((180, 40, 40))
    pygame.draw.circle(icon_surf, (80, 180, 80), (16, 16), 10)
    pygame.display.set_icon(icon_surf)

    game = Game(screen)
    clock = pygame.time.Clock()
    running = True

    while running:
        running = game.handle_events()
        
        if game.state == "playing":
            game.update()
            
        game.draw()
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()
