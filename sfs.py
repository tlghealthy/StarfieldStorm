"""
starfield_storm.py

A single-file 2D bullet hell game in Python + Pygame, loading constants
and sprites (with scaling/offsets) from 'settings.json'.

Highlights:
1. Sprites are loaded from config["sprites"].
2. Each sprite entry in the JSON can specify:
   - "path": relative/absolute filepath to the image (PNG/JPG/etc.).
   - "scale": [width, height] to scale the sprite after loading.
   - "offset": [offset_x, offset_y], used to center or position the sprite 
       relative to the object's x,y in the game.
3. If a sprite file is missing, we fallback to drawing a colored shape.

Prerequisites:
    pip install pygame

Usage:
    python starfield_storm.py
"""

import pygame
import random
import math
import sys
import json
import os


SETTINGS_FILE = "settings.json"

with open(SETTINGS_FILE, "r") as f:
    config = json.load(f)

# Window settings
WIN_WIDTH = config["window"]["width"]
WIN_HEIGHT = config["window"]["height"]
FPS = config["window"]["fps"]

# Basic colors (for fallback or UI)
COLOR_BLACK = tuple(config["colors"]["BLACK"])
COLOR_WHITE = tuple(config["colors"]["WHITE"])

pygame.init()
pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))

###############################################################################
# SPRITE LOADING
###############################################################################
def load_sprites_from_config(sprite_conf):
    """
    Reads the "sprites" section of settings.json.
    Returns a dict of:
      {
        "player_ship": {
          "surface": <pygame.Surface or fallback>,
          "offset": (offset_x, offset_y)
        },
        "enemy_ship": {...},
        ...
      }
    """
    loaded = {}
    for sprite_name, info in sprite_conf.items():
        # Expected keys: "path", "scale", "offset"
        path = info.get("path", "")
        scale = info.get("scale", [32, 32])   # default 32x32
        offset = info.get("offset", [16, 16]) # default half of scale

        if path and os.path.isfile(path):
            # Load image
            surf = pygame.image.load(path).convert_alpha()
            # Scale if needed
            if scale:
                w, h = scale
                surf = pygame.transform.scale(surf, (w, h))
        else:
            # Fallback: create a placeholder if file not found
            w, h = scale
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            # semi-transparent magenta for fallback
            surf.fill((255, 0, 255, 128))
            print(f"Warning: Sprite file not found or missing path for '{sprite_name}' -> using fallback")

        # Store in dictionary
        loaded[sprite_name] = {
            "surface": surf,
            "offset": tuple(offset)
        }
    return loaded

###############################################################################
# GLOBAL: LOAD ALL SPRITES
###############################################################################
sprite_conf = config.get("sprites", {})
loaded_sprites = load_sprites_from_config(sprite_conf)

###############################################################################
# GAME CLASSES
###############################################################################
class Player:
    def __init__(self):
        p = config["player"]
        self.radius = p["radius"]
        self.x = WIN_WIDTH // 2
        self.y = WIN_HEIGHT // 2
        self.health = p["initial_health"]
        self.color = tuple(p["color"])
        self.fire_delay = p["fire_delay_ms"]
        self.last_shot_time = pygame.time.get_ticks()
        self.max_speed = p["max_speed"]
        self.collision_with_enemy_damage = p["collision_with_enemy_damage"]

        # Sprite references (optional fallback if missing in config)
        self.sprite_key = "player_ship"
        if self.sprite_key in loaded_sprites:
            self.sprite_surf = loaded_sprites[self.sprite_key]["surface"]
            self.sprite_offset = loaded_sprites[self.sprite_key]["offset"]
        else:
            self.sprite_surf = None
            self.sprite_offset = (self.radius, self.radius)

    def update(self):
        """Move player toward the mouse cursor but clamp to max speed."""
        mouse_x, mouse_y = pygame.mouse.get_pos()
        dx = mouse_x - self.x
        dy = mouse_y - self.y
        dist = math.hypot(dx, dy)

        if dist > 0:
            if dist > self.max_speed:
                scale = self.max_speed / dist
                dx *= scale
                dy *= scale
            self.x += dx
            self.y += dy

        # Clamp to screen boundaries
        self.x = max(self.radius, min(WIN_WIDTH - self.radius, self.x))
        self.y = max(self.radius, min(WIN_HEIGHT - self.radius, self.y))

    def shoot(self, bullets):
        now = pygame.time.get_ticks()
        if now - self.last_shot_time >= self.fire_delay:
            bullet_conf = config["bullet"]
            bullets.append(Bullet(
                x=self.x,
                y=self.y,
                dx=0,
                dy=bullet_conf["player_bullet_speed_y"],
                color=tuple(bullet_conf["player_bullet_color"]),
                from_player=True
            ))
            self.last_shot_time = now

    def draw(self, screen):
        if self.sprite_surf:
            # Use sprite with offset
            offset_x, offset_y = self.sprite_offset
            draw_x = int(self.x - offset_x)
            draw_y = int(self.y - offset_y)
            screen.blit(self.sprite_surf, (draw_x, draw_y))
        else:
            # fallback shape
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        
        # 2. Draw the collision circle on top (optional debug)
        debug_collisions = config.get("debug", {}).get("show_collision_circles", False)
        if debug_collisions:
            # A thin red circle outline, width=1
            pygame.draw.circle(screen, (255, 0, 0), (int(self.x), int(self.y)), self.radius, width=1)


class Bullet:
    def __init__(self, x, y, dx, dy, color, from_player=False):
        b = config["bullet"]
        self.radius = b["radius"]
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.color = color
        self.from_player = from_player

        # Optional: use separate sprite for bullet
        if from_player:
            self.sprite_key = "player_bullet"
        else:
            self.sprite_key = "enemy_bullet"

        if self.sprite_key in loaded_sprites:
            self.sprite_surf = loaded_sprites[self.sprite_key]["surface"]
            self.sprite_offset = loaded_sprites[self.sprite_key]["offset"]
        else:
            self.sprite_surf = None
            self.sprite_offset = (self.radius, self.radius)

    def update(self):
        self.x += self.dx
        self.y += self.dy

    def draw(self, screen):
        if self.sprite_surf:
            offset_x, offset_y = self.sprite_offset
            screen.blit(self.sprite_surf, (int(self.x - offset_x), int(self.y - offset_y)))
        else:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
            
        # 2. Draw the collision circle on top (optional debug)
        debug_collisions = config.get("debug", {}).get("show_collision_circles", False)
        if debug_collisions:
            # A thin red circle outline, width=1
            pygame.draw.circle(screen, (255, 0, 0), (int(self.x), int(self.y)), self.radius, width=1)

    def off_screen(self):
        return (self.x < 0 or self.x > WIN_WIDTH or self.y < 0 or self.y > WIN_HEIGHT)


class Enemy:
    def __init__(self, x, y, speed, difficulty):
        e = config["enemy"]
        self.radius = e["radius"]
        self.color = tuple(e["color"])
        self.health = e["initial_health"]
        self.fire_delay = e["fire_delay_ms"]
        self.last_shot_time = pygame.time.get_ticks()

        self.x = x
        self.y = y
        self.speed = speed
        self.difficulty = difficulty

        # Sprites
        self.sprite_key = "enemy_ship"
        if self.sprite_key in loaded_sprites:
            self.sprite_surf = loaded_sprites[self.sprite_key]["surface"]
            self.sprite_offset = loaded_sprites[self.sprite_key]["offset"]
        else:
            self.sprite_surf = None
            self.sprite_offset = (self.radius, self.radius)

    def update(self, bullets, player):
        # Move downward
        self.y += self.speed

        # Fire bullets
        now = pygame.time.get_ticks()
        if now - self.last_shot_time >= self.fire_delay:
            bullet_conf = config["bullet"]
            angle = math.atan2(player.y - self.y, player.x - self.x)
            bullet_speed = bullet_conf["enemy_bullet_base_speed"] + (self.difficulty * 0.1)
            dx = bullet_speed * math.cos(angle)
            dy = bullet_speed * math.sin(angle)
            bullets.append(Bullet(
                x=self.x,
                y=self.y,
                dx=dx,
                dy=dy,
                color=tuple(bullet_conf["enemy_bullet_color"]),
                from_player=False
            ))
            self.last_shot_time = now

    def draw(self, screen):
        if self.sprite_surf:
            offset_x, offset_y = self.sprite_offset
            screen.blit(self.sprite_surf, (int(self.x - offset_x), int(self.y - offset_y)))
        else:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        # 2. Draw the collision circle on top (optional debug)
        debug_collisions = config.get("debug", {}).get("show_collision_circles", False)
        if debug_collisions:
            # A thin red circle outline, width=1
            pygame.draw.circle(screen, (255, 0, 0), (int(self.x), int(self.y)), self.radius, width=1)

    def off_screen(self):
        return (self.y > WIN_HEIGHT + self.radius)


class Obstacle:
    def __init__(self):
        o = config["obstacle"]
        self.radius = random.randint(o["radius_min"], o["radius_max"])
        self.color = tuple(o["color"])
        self.health = o["initial_health"]
        self.x = random.randint(self.radius, WIN_WIDTH - self.radius)
        self.y = -self.radius
        self.speed = random.uniform(o["speed_min"], o["speed_max"])
        self.collision_damage = o["collision_damage"]

        # Sprites
        self.sprite_key = "obstacle"
        if self.sprite_key in loaded_sprites:
            self.sprite_surf = loaded_sprites[self.sprite_key]["surface"]
            self.sprite_offset = loaded_sprites[self.sprite_key]["offset"]
        else:
            self.sprite_surf = None
            self.sprite_offset = (self.radius, self.radius)

    def update(self):
        self.y += self.speed

    def draw(self, screen):
        if self.sprite_surf:
            offset_x, offset_y = self.sprite_offset
            screen.blit(self.sprite_surf, (int(self.x - offset_x), int(self.y - offset_y)))
        else:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        # 2. Draw the collision circle on top (optional debug)
        debug_collisions = config.get("debug", {}).get("show_collision_circles", False)
        if debug_collisions:
            # A thin red circle outline, width=1
            pygame.draw.circle(screen, (255, 0, 0), (int(self.x), int(self.y)), self.radius, width=1)

    def off_screen(self):
        return (self.y > WIN_HEIGHT + self.radius)


class HealthPickup:
    """Floating item that restores some health if collected by the player."""
    def __init__(self):
        p = config["pickup"]
        self.radius = p["radius"]
        self.color = tuple(p["color"])
        self.x = random.randint(self.radius, WIN_WIDTH - self.radius)
        self.y = -self.radius
        self.speed = random.uniform(p["speed_min"], p["speed_max"])
        self.restore_amount = p["restore_amount"]

        # Sprites
        self.sprite_key = "health_pickup"
        if self.sprite_key in loaded_sprites:
            self.sprite_surf = loaded_sprites[self.sprite_key]["surface"]
            self.sprite_offset = loaded_sprites[self.sprite_key]["offset"]
        else:
            self.sprite_surf = None
            self.sprite_offset = (self.radius, self.radius)

    def update(self):
        self.y += self.speed

    def draw(self, screen):
        if self.sprite_surf:
            offset_x, offset_y = self.sprite_offset
            screen.blit(self.sprite_surf, (int(self.x - offset_x), int(self.y - offset_y)))
        else:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        # 2. Draw the collision circle on top (optional debug)
        debug_collisions = config.get("debug", {}).get("show_collision_circles", False)
        if debug_collisions:
            # A thin red circle outline, width=1
            pygame.draw.circle(screen, (255, 0, 0), (int(self.x), int(self.y)), self.radius, width=1)

    def off_screen(self):
        return (self.y > WIN_HEIGHT + self.radius)

###############################################################################
# MAIN GAME CLASS
###############################################################################
class Game:
    def __init__(self):
        
        self.screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
        pygame.display.set_caption("Starfield Storm w/ Sprites & JSON Settings")
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "MENU"
        
        self.player = Player()
        self.bullets = []
        self.enemies = []
        self.obstacles = []
        self.pickups = []

        self.score = 0

        diff_conf = config["difficulty"]
        self.wave_interval = diff_conf["wave_interval_start_ms"]
        self.wave_interval_min = diff_conf["wave_interval_min_ms"]
        self.wave_interval_decrement = diff_conf["wave_interval_decrement_ms"]
        self.last_wave_time = pygame.time.get_ticks()

        # For starfield background
        self.stars = [
            (random.randint(0, WIN_WIDTH), random.randint(0, WIN_HEIGHT))
            for _ in range(100)
        ]
    
    def run(self):
        while self.running:
            if self.state == "MENU":
                self.menu_loop()
            elif self.state == "GAME":
                self.game_loop()
            elif self.state == "GAME_OVER":
                self.game_over_loop()
        pygame.quit()
        sys.exit()

    def menu_loop(self):
        self.screen.fill(COLOR_BLACK)
        self.draw_text("STARFIELD STORM (Sprites & JSON)", 50, WIN_WIDTH // 2, WIN_HEIGHT // 2 - 90, COLOR_WHITE)
        self.draw_text("Press [SPACE] to START or [Q] to QUIT", 24, WIN_WIDTH // 2, WIN_HEIGHT // 2 - 40, COLOR_WHITE)

        # Controls explanation:
        self.draw_text("CONTROLS:", 24, WIN_WIDTH // 2, WIN_HEIGHT // 2 + 10, COLOR_WHITE)
        self.draw_text("Move the mouse to steer your ship (speed limited).", 20, WIN_WIDTH // 2, WIN_HEIGHT // 2 + 40, COLOR_WHITE)
        self.draw_text("Ship fires automatically. Avoid enemies & obstacles.", 20, WIN_WIDTH // 2, WIN_HEIGHT // 2 + 65, COLOR_WHITE)
        self.draw_text("Collect pink orbs to restore health.", 20, WIN_WIDTH // 2, WIN_HEIGHT // 2 + 90, COLOR_WHITE)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self.reset_game()
                    self.state = "GAME"

    def game_over_loop(self):
        self.screen.fill(COLOR_BLACK)
        self.draw_text("GAME OVER", 50, WIN_WIDTH // 2, WIN_HEIGHT // 2 - 50, (255, 0, 0))
        self.draw_text(f"FINAL SCORE: {int(self.score)}", 24, WIN_WIDTH // 2, WIN_HEIGHT // 2, COLOR_WHITE)
        self.draw_text("Press [R] to RESTART or [Q] to QUIT", 24, WIN_WIDTH // 2, WIN_HEIGHT // 2 + 50, COLOR_WHITE)
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    self.running = False
                elif event.key == pygame.K_r:
                    self.reset_game()
                    self.state = "GAME"

    def game_loop(self):
        dt = self.clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

        # Update background starfield
        self.update_stars()

        # Update player
        self.player.update()
        self.player.shoot(self.bullets)

        # Difficulty scale
        diff_conf = config["difficulty"]
        elapsed_time = pygame.time.get_ticks()
        difficulty = (elapsed_time // diff_conf["time_scale_ms"])
        self.score += 0.03  # small passive score increment

        # Wave spawn
        if elapsed_time - self.last_wave_time >= self.wave_interval:
            self.spawn_enemies(difficulty)
            self.spawn_obstacles(difficulty)
            self.spawn_health_pickups()
            self.last_wave_time = elapsed_time
            self.wave_interval = max(self.wave_interval_min, self.wave_interval - self.wave_interval_decrement)

        # Update bullets
        for b in self.bullets[:]:
            b.update()
            if b.off_screen():
                self.bullets.remove(b)

        # Update enemies
        for e in self.enemies[:]:
            e.update(self.bullets, self.player)
            if e.off_screen():
                self.enemies.remove(e)

        # Update obstacles
        for o in self.obstacles[:]:
            o.update()
            if o.off_screen():
                self.obstacles.remove(o)

        # Update pickups
        for p in self.pickups[:]:
            p.update()
            if p.off_screen():
                self.pickups.remove(p)

        # Collision detection
        self.handle_collisions()

        # Check game over
        if self.player.health <= 0:
            self.state = "GAME_OVER"

        # Draw all
        self.draw_game()
        pygame.display.flip()

    def spawn_enemies(self, difficulty):
        diff_conf = config["difficulty"]
        enemy_count = 1 + int(difficulty * diff_conf["enemy_spawn_factor"])
        e_conf = config["enemy"]

        for _ in range(enemy_count):
            x = random.randint(20, WIN_WIDTH - 20)
            y = -30
            speed = e_conf["base_speed"] + difficulty * 0.05
            self.enemies.append(Enemy(x, y, speed, difficulty))

    def spawn_obstacles(self, difficulty):
        diff_conf = config["difficulty"]
        obstacle_count = max(1, int(difficulty // diff_conf["obstacle_spawn_factor"]))
        for _ in range(obstacle_count):
            self.obstacles.append(Obstacle())

    def spawn_health_pickups(self):
        diff_conf = config["difficulty"]
        if random.random() < diff_conf["pickup_chance"]:
            self.pickups.append(HealthPickup())

    def handle_collisions(self):
        bullet_conf = config["bullet"]
        enemy_bullet_damage = bullet_conf["enemy_bullet_damage"]

        # Bullets vs Enemies
        for b in self.bullets[:]:
            if b.from_player:
                for e in self.enemies[:]:
                    if self.distance(b.x, b.y, e.x, e.y) < (b.radius + e.radius):
                        e.health -= 1
                        if e.health <= 0:
                            self.enemies.remove(e)
                            self.score += 10
                        if b in self.bullets:
                            self.bullets.remove(b)
                        break
                for o in self.obstacles[:]:
                    if self.distance(b.x, b.y, o.x, o.y) < (b.radius + o.radius):
                        o.health -= 1
                        if o.health <= 0:
                            self.obstacles.remove(o)
                            self.score += 10
                        if b in self.bullets:
                            self.bullets.remove(b)
                        break

        # Enemy bullets vs Player
        for b in self.bullets[:]:
            if not b.from_player:
                if self.distance(b.x, b.y, self.player.x, self.player.y) < (b.radius + self.player.radius):
                    self.player.health -= enemy_bullet_damage
                    if b in self.bullets:
                        self.bullets.remove(b)

        # Obstacles vs Player
        for o in self.obstacles[:]:
            if self.distance(o.x, o.y, self.player.x, self.player.y) < (o.radius + self.player.radius):
                self.player.health -= o.collision_damage
                if o in self.obstacles:
                    self.obstacles.remove(o)

        # Enemies vs Player
        for e in self.enemies[:]:
            if self.distance(e.x, e.y, self.player.x, self.player.y) < (e.radius + self.player.radius):
                self.player.health -= self.player.collision_with_enemy_damage
                if e in self.enemies:
                    self.enemies.remove(e)

        # Health pickups vs Player
        for p in self.pickups[:]:
            if self.distance(p.x, p.y, self.player.x, self.player.y) < (p.radius + self.player.radius):
                self.player.health += p.restore_amount
                self.player.health = min(self.player.health, config["player"]["initial_health"])
                self.pickups.remove(p)

    def distance(self, x1, y1, x2, y2):
        return math.hypot(x2 - x1, y2 - y1)

    def update_stars(self):
        new_stars = []
        for (sx, sy) in self.stars:
            sy += 2
            if sy > WIN_HEIGHT:
                sy = 0
                sx = random.randint(0, WIN_WIDTH)
            new_stars.append((sx, sy))
        self.stars = new_stars

    def draw_game(self):
        self.screen.fill(COLOR_BLACK)
        # Draw starfield
        for (sx, sy) in self.stars:
            pygame.draw.circle(self.screen, COLOR_WHITE, (sx, sy), 2)

        # Player
        self.player.draw(self.screen)
        # Bullets
        for b in self.bullets:
            b.draw(self.screen)
        # Enemies
        for e in self.enemies:
            e.draw(self.screen)
        # Obstacles
        for o in self.obstacles:
            o.draw(self.screen)
        # Pickups
        for p in self.pickups:
            p.draw(self.screen)

        # UI
        self.draw_text(f"Score: {int(self.score)}", 24, 50, 20, COLOR_WHITE, align="left")
        self.draw_text(f"Health: {self.player.health}", 24, WIN_WIDTH - 150, 20, COLOR_WHITE, align="left")

    def draw_text(self, text, size, x, y, color, align="center"):
        font = pygame.font.SysFont(None, size)
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        if align == "center":
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surface, rect)

    def reset_game(self):
        self.player = Player()
        self.bullets = []
        self.enemies = []
        self.obstacles = []
        self.pickups = []
        self.score = 0

        diff_conf = config["difficulty"]
        self.wave_interval = diff_conf["wave_interval_start_ms"]
        self.wave_interval_min = diff_conf["wave_interval_min_ms"]
        self.wave_interval_decrement = diff_conf["wave_interval_decrement_ms"]
        self.last_wave_time = pygame.time.get_ticks()

        self.stars = [
            (random.randint(0, WIN_WIDTH), random.randint(0, WIN_HEIGHT))
            for _ in range(100)
        ]

def main():
    game = Game()
    game.run()

if __name__ == "__main__":
    main()
