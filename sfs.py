"""
starfield_storm.py

A single-file 2D bullet hell game in Python + Pygame, loading key constants
and values from 'settings.json' for easy tweaking, now with Controls Explanation
on the Start (Menu) screen.

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

# Load settings from JSON
SETTINGS_FILE = "settings.json"

with open(SETTINGS_FILE, "r") as f:
    config = json.load(f)

# Pull top-level config
WIN_WIDTH = config["window"]["width"]
WIN_HEIGHT = config["window"]["height"]
FPS = config["window"]["fps"]

# Grab some extra color references if desired
COLOR_BLACK = tuple(config["colors"]["BLACK"])
COLOR_WHITE = tuple(config["colors"]["WHITE"])

class Player:
    def __init__(self):
        p = config["player"]  # shortcut
        self.radius = p["radius"]
        self.x = WIN_WIDTH // 2
        self.y = WIN_HEIGHT // 2
        self.health = p["initial_health"]
        self.color = tuple(p["color"])
        self.fire_delay = p["fire_delay_ms"]  # ms between shots
        self.last_shot_time = pygame.time.get_ticks()
        self.max_speed = p["max_speed"]
        self.collision_with_enemy_damage = p["collision_with_enemy_damage"]

    def update(self):
        """Move player toward the mouse cursor but clamp to max speed."""
        mouse_x, mouse_y = pygame.mouse.get_pos()
        dx = mouse_x - self.x
        dy = mouse_y - self.y
        dist = math.hypot(dx, dy)
        if dist > 0:
            # Limit movement to max_speed
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
        """Continuously fire bullets if enough time has passed."""
        now = pygame.time.get_ticks()
        if now - self.last_shot_time >= self.fire_delay:
            bullet_conf = config["bullet"]
            # Spawn a new bullet from the player's position
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
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

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

    def update(self):
        self.x += self.dx
        self.y += self.dy

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

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

    def update(self, bullets, player):
        # Move downward (or a simple pattern)
        self.y += self.speed
        
        # Possibly fire bullets
        now = pygame.time.get_ticks()
        if now - self.last_shot_time >= self.fire_delay:
            bullet_conf = config["bullet"]
            angle = math.atan2(player.y - self.y, player.x - self.x)
            # base speed + (some scaling * difficulty)
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
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

    def off_screen(self):
        return (self.y > WIN_HEIGHT + self.radius)

class Obstacle:
    def __init__(self):
        o = config["obstacle"]
        self.radius = random.randint(o["radius_min"], o["radius_max"])
        self.color = tuple(o["color"])
        self.x = random.randint(self.radius, WIN_WIDTH - self.radius)
        self.y = -self.radius
        self.speed = random.uniform(o["speed_min"], o["speed_max"])
        self.collision_damage = o["collision_damage"]

    def update(self):
        self.y += self.speed

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

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

    def update(self):
        self.y += self.speed

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

    def off_screen(self):
        return (self.y > WIN_HEIGHT + self.radius)

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
        pygame.display.set_caption("Starfield Storm w/ JSON Settings")
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
        self.draw_text("STARFIELD STORM (JSON Settings)", 50, WIN_WIDTH // 2, WIN_HEIGHT // 2 - 90, COLOR_WHITE)
        self.draw_text("Press [SPACE] to START or [Q] to QUIT", 24, WIN_WIDTH // 2, WIN_HEIGHT // 2 - 40, COLOR_WHITE)

        # Controls explanation added here:
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
        # Continuous shooting
        self.player.shoot(self.bullets)

        # Difficulty scales: increments every X ms from settings
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
            # Gradually decrease wave interval
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

        # Update health pickups
        for p in self.pickups[:]:
            p.update()
            if p.off_screen():
                self.pickups.remove(p)

        # Collision detection
        self.handle_collisions()

        # Check game over
        if self.player.health <= 0:
            self.state = "GAME_OVER"

        # Draw everything
        self.draw_game()
        pygame.display.flip()

    def spawn_enemies(self, difficulty):
        """Spawn a wave of enemies based on difficulty."""
        diff_conf = config["difficulty"]
        enemy_count = 1 + int(difficulty * diff_conf["enemy_spawn_factor"])
        e_conf = config["enemy"]

        for _ in range(enemy_count):
            x = random.randint(20, WIN_WIDTH - 20)
            y = -30
            # base_speed plus some scaling
            speed = e_conf["base_speed"] + difficulty * 0.05
            self.enemies.append(Enemy(x, y, speed, difficulty))

    def spawn_obstacles(self, difficulty):
        """Spawn some obstacles based on difficulty."""
        diff_conf = config["difficulty"]
        obstacle_count = max(1, int(difficulty // diff_conf["obstacle_spawn_factor"]))
        for _ in range(obstacle_count):
            self.obstacles.append(Obstacle())

    def spawn_health_pickups(self):
        """Small random chance each wave to spawn a health pickup."""
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
                # Destroy obstacle after collision
                if o in self.obstacles:
                    self.obstacles.remove(o)

        # Enemies vs Player
        for e in self.enemies[:]:
            if self.distance(e.x, e.y, self.player.x, self.player.y) < (e.radius + self.player.radius):
                # Player takes damage from collision
                self.player.health -= self.player.collision_with_enemy_damage
                # Enemy is destroyed on collision
                if e in self.enemies:
                    self.enemies.remove(e)

        # Health Pickups vs Player
        for p in self.pickups[:]:
            if self.distance(p.x, p.y, self.player.x, self.player.y) < (p.radius + self.player.radius):
                self.player.health += p.restore_amount
                # Optionally cap player's health
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

        # Draw player
        self.player.draw(self.screen)

        # Draw bullets
        for b in self.bullets:
            b.draw(self.screen)

        # Draw enemies
        for e in self.enemies:
            e.draw(self.screen)

        # Draw obstacles
        for o in self.obstacles:
            o.draw(self.screen)

        # Draw health pickups
        for p in self.pickups:
            p.draw(self.screen)

        # UI: Score and Health
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
