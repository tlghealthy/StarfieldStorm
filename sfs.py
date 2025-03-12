import pygame, random, math, sys, json, os

# ----- CONFIG & INITIALIZATION -----
with open("settings.json", "r") as f:
    config = json.load(f)
WIN_WIDTH, WIN_HEIGHT, FPS = config["window"]["width"], config["window"]["height"], config["window"]["fps"]
COLOR_BLACK, COLOR_WHITE = tuple(config["colors"]["BLACK"]), tuple(config["colors"]["WHITE"])

pygame.init()
screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
pygame.mixer.init()

# Load background music and sound effects
bg_music = config.get("audio", {}).get("bg_music_path", "")
sfx_conf = config.get("audio", {}).get("effects", {})
sound_effects = {name: (pygame.mixer.Sound(path) if os.path.isfile(path) else None)
                 for name, path in sfx_conf.items()}
if bg_music and os.path.isfile(bg_music):
    pygame.mixer.music.load(bg_music)
    pygame.mixer.music.play(-1)
else:
    print("Warning: No valid background music provided.")

# ----- SPRITE LOADING -----
def load_sprites(sprite_conf):
    sprites = {}
    for name, info in sprite_conf.items():
        path, scale = info.get("path", ""), info.get("scale", [32, 32])
        offset, z = tuple(info.get("offset", [16, 16])), info.get("z_order", 0)
        if path and os.path.isfile(path):
            surf = pygame.image.load(path).convert_alpha()
            surf = pygame.transform.scale(surf, tuple(scale)) if scale else surf
        else:
            surf = pygame.Surface(tuple(scale), pygame.SRCALPHA)
            surf.fill((255, 0, 255, 128))
            print(f"Warning: Sprite '{name}' not found; using fallback")
        sprites[name] = {"surface": surf, "offset": offset, "z_order": z}
    return sprites

loaded_sprites = load_sprites(config.get("sprites", {}))

# Helper for drawing entities (sprite if available, else a circle with optional debug outline)
def draw_entity(screen, ent):
    if getattr(ent, "sprite_surf", None):
        screen.blit(ent.sprite_surf, (int(ent.x - ent.sprite_offset[0]), int(ent.y - ent.sprite_offset[1])))
    else:
        pygame.draw.circle(screen, ent.color, (int(ent.x), int(ent.y)), ent.radius)
    if config.get("debug", {}).get("show_collision_circles", False):
        pygame.draw.circle(screen, (255, 0, 0), (int(ent.x), int(ent.y)), ent.radius, 1)

# ----- GAME OBJECTS -----
class Player:
    def __init__(self):
        p = config["player"]
        self.radius, self.x, self.y = p["radius"], WIN_WIDTH // 2, WIN_HEIGHT // 2
        self.health, self.color = p["initial_health"], tuple(p["color"])
        self.fire_delay, self.last_shot = p["fire_delay_ms"], pygame.time.get_ticks()
        self.max_speed, self.collision_damage = p["max_speed"], p["collision_with_enemy_damage"]
        self.base_fire, self.base_speed = self.fire_delay, self.max_speed
        self.active_powerups = {}
        key = "player_ship"
        if key in loaded_sprites:
            data = loaded_sprites[key]
            self.sprite_surf, self.sprite_offset, self.z_order = data["surface"], data["offset"], data["z_order"]
        else:
            self.sprite_surf, self.sprite_offset, self.z_order = None, (self.radius, self.radius), 0

    def update(self):
        self.handle_powerups()
        mx, my = pygame.mouse.get_pos()
        dx, dy = mx - self.x, my - self.y
        if (dist := math.hypot(dx, dy)) > 0:
            if dist > self.max_speed:
                dx, dy = dx * self.max_speed / dist, dy * self.max_speed / dist
            self.x, self.y = self.x + dx, self.y + dy
        self.x = max(self.radius, min(WIN_WIDTH - self.radius, self.x))
        self.y = max(self.radius, min(WIN_HEIGHT - self.radius, self.y))

    def handle_powerups(self):
        now = pygame.time.get_ticks()
        for ptype in list(self.active_powerups):
            if now >= self.active_powerups[ptype]:
                del self.active_powerups[ptype]
        self.fire_delay, self.max_speed = self.base_fire, self.base_speed
        if "rapid_fire" in self.active_powerups:
            self.fire_delay = int(self.base_fire * config["powerups"]["rapid_fire"]["fire_delay_factor"])
        if "speed_boost" in self.active_powerups:
            self.max_speed = self.base_speed * config["powerups"]["speed_boost"]["speed_multiplier"]

    def shoot(self, bullets):
        now = pygame.time.get_ticks()
        if now - self.last_shot >= self.fire_delay:
            bconf = config["bullet"]
            if sound_effects.get("shoot"):
                sound_effects["shoot"].play()
            if "spread_shot" in self.active_powerups:
                sconf = config["powerups"]["spread_shot"]
                count, angle_deg = sconf["bullet_count"], sconf["angle_degrees"]
                start_angle = -((count - 1) * angle_deg) / 2
                for i in range(count):
                    angle = math.radians(start_angle + i * angle_deg)
                    base_speed = -bconf["player_bullet_speed_y"]
                    dx = base_speed * math.sin(angle)
                    dy = base_speed * -math.cos(angle)
                    bullets.append(Bullet(self.x, self.y, dx, dy, tuple(bconf["player_bullet_color"]), True))
            else:
                bullets.append(Bullet(self.x, self.y, 0, bconf["player_bullet_speed_y"], tuple(bconf["player_bullet_color"]), True))
            self.last_shot = now

    def draw(self, screen):
        draw_entity(screen, self)

    def is_shielded(self):
        return "shield" in self.active_powerups

    def apply_powerup(self, ptype, duration):
        self.active_powerups[ptype] = pygame.time.get_ticks() + duration

class Bullet:
    def __init__(self, x, y, dx, dy, color, from_player=False):
        b = config["bullet"]
        self.radius, self.x, self.y = b["radius"], x, y
        self.dx, self.dy, self.color = dx, dy, color
        self.from_player = from_player
        key = "player_bullet" if from_player else "enemy_bullet"
        if key in loaded_sprites:
            data = loaded_sprites[key]
            self.sprite_surf, self.sprite_offset, self.z_order = data["surface"], data["offset"], data["z_order"]
        else:
            self.sprite_surf, self.sprite_offset, self.z_order = None, (self.radius, self.radius), 0

    def update(self):
        self.x += self.dx; self.y += self.dy

    def draw(self, screen):
        draw_entity(screen, self)

    def off_screen(self):
        return self.x < 0 or self.x > WIN_WIDTH or self.y < 0 or self.y > WIN_HEIGHT

class Enemy:
    def __init__(self, x, y, speed, difficulty):
        e = config["enemy"]
        self.radius, self.color, self.health = e["radius"], tuple(e["color"]), e["initial_health"]
        self.fire_delay, self.last_shot = e["fire_delay_ms"], pygame.time.get_ticks()
        self.x, self.y, self.speed, self.difficulty = x, y, speed, difficulty
        key = "enemy_ship"
        if key in loaded_sprites:
            data = loaded_sprites[key]
            self.sprite_surf, self.sprite_offset, self.z_order = data["surface"], data["offset"], data["z_order"]
        else:
            self.sprite_surf, self.sprite_offset, self.z_order = None, (self.radius, self.radius), 0

    def update(self, bullets, player):
        self.y += self.speed
        if pygame.time.get_ticks() - self.last_shot >= self.fire_delay:
            angle = math.atan2(player.y - self.y, player.x - self.x)
            bconf = config["bullet"]
            bullet_speed = bconf["enemy_bullet_base_speed"] + self.difficulty * 0.1
            dx, dy = bullet_speed * math.cos(angle), bullet_speed * math.sin(angle)
            bullets.append(Bullet(self.x, self.y, dx, dy, tuple(bconf["enemy_bullet_color"])))
            self.last_shot = pygame.time.get_ticks()

    def draw(self, screen):
        draw_entity(screen, self)

    def off_screen(self):
        return self.y > WIN_HEIGHT + self.radius

class Obstacle:
    def __init__(self):
        o = config["obstacle"]
        self.radius = random.randint(o["radius_min"], o["radius_max"])
        self.color, self.health = tuple(o["color"]), o["initial_health"]
        self.x = random.randint(self.radius, WIN_WIDTH - self.radius)
        self.y, self.speed = -self.radius, random.uniform(o["speed_min"], o["speed_max"])
        self.collision_damage = o["collision_damage"]
        key = "obstacle"
        if key in loaded_sprites:
            base = loaded_sprites[key]["surface"]
            self.sprite_surf = pygame.transform.scale(base, (2 * self.radius, 2 * self.radius))
            self.sprite_offset, self.z_order = (self.radius, self.radius), loaded_sprites[key]["z_order"]
        else:
            self.sprite_surf, self.sprite_offset, self.z_order = None, (self.radius, self.radius), 0

    def update(self):
        self.y += self.speed

    def draw(self, screen):
        draw_entity(screen, self)

    def off_screen(self):
        return self.y > WIN_HEIGHT + self.radius

class HealthPickup:
    def __init__(self):
        p = config["pickup"]
        self.radius = p["radius"]
        self.color = tuple(p["color"])
        self.x = random.randint(self.radius, WIN_WIDTH - self.radius)
        self.y = -self.radius
        self.speed = random.uniform(p["speed_min"], p["speed_max"])
        self.restore = p["restore_amount"]
        key = "health_pickup"
        if key in loaded_sprites:
            data = loaded_sprites[key]
            self.sprite_surf, self.sprite_offset, self.z_order = data["surface"], data["offset"], data["z_order"]
        else:
            self.sprite_surf, self.sprite_offset, self.z_order = None, (self.radius, self.radius), 0

    def update(self):
        self.y += self.speed

    def draw(self, screen):
        draw_entity(screen, self)

    def off_screen(self):
        return self.y > WIN_HEIGHT + self.radius

class Powerup:
    def __init__(self, ptype):
        self.ptype = ptype
        pconf = config["powerups"][ptype]
        self.base_duration = pconf["duration"]
        self.color = tuple(pconf.get("color", [255, 255, 255]))
        self.rarity = self.pick_rarity()
        rar_conf = config["powerups"]["rarities"][self.rarity]
        self.duration = int(self.base_duration * rar_conf["duration_multiplier"])
        self.outline_color, self.outline_thickness = tuple(rar_conf["outline_color"]), rar_conf["outline_thickness"]
        self.radius = 16
        self.x = random.randint(self.radius, WIN_WIDTH - self.radius)
        self.y = -self.radius
        self.speed, self.z_order = random.uniform(1.0, 2.0), 3
        self.sprite_surf, self.sprite_offset = None, (self.radius, self.radius)
        if (path := pconf.get("sprite_path", "")) and os.path.isfile(path):
            surf = pygame.image.load(path).convert_alpha()
            self.sprite_surf = pygame.transform.scale(surf, (2 * self.radius, 2 * self.radius))

    def pick_rarity(self):
        rar = config["powerups"]["rarities"]
        total = rar["common"]["weight"] + rar["uncommon"]["weight"] + rar["rare"]["weight"]
        roll = random.random() * total
        if roll < rar["common"]["weight"]:
            return "common"
        roll -= rar["common"]["weight"]
        return "uncommon" if roll < rar["uncommon"]["weight"] else "rare"

    def update(self):
        self.y += self.speed

    def draw(self, screen):
        cx, cy = int(self.x), int(self.y)
        pygame.draw.circle(screen, self.outline_color, (cx, cy), self.radius + self.outline_thickness)
        if self.sprite_surf:
            screen.blit(self.sprite_surf, (cx - self.radius, cy - self.radius))
        else:
            pygame.draw.circle(screen, self.color, (cx, cy), self.radius)
        if config.get("debug", {}).get("show_collision_circles", False):
            pygame.draw.circle(screen, (255, 0, 0), (cx, cy), self.radius, 1)

    def off_screen(self):
        return self.y > WIN_HEIGHT + self.radius

# ----- GAME CLASS -----
class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
        pygame.display.set_caption("Starfield Storm w/ Distinct SFX")
        self.clock, self.running, self.state = pygame.time.Clock(), True, "MENU"
        self.reset_game()
        self.score = 0
        self.last_wave = pygame.time.get_ticks()
        diff = config["difficulty"]
        self.wave_interval, self.wave_interval_min, self.wave_decr = diff["wave_interval_start_ms"], diff["wave_interval_min_ms"], diff["wave_interval_decrement_ms"]
        self.stars = [(random.randint(0, WIN_WIDTH), random.randint(0, WIN_HEIGHT)) for _ in range(100)]

    def reset_game(self):
        self.player = Player()
        self.bullets, self.enemies = [], []
        self.obstacles, self.pickups, self.powerups = [], [], []
        self.score = 0

    def run(self):
        while self.running:
            {"MENU": self.menu_loop, "GAME": self.game_loop, "GAME_OVER": self.game_over_loop}[self.state]()
        pygame.quit(); sys.exit()

    def menu_loop(self):
        self.screen.fill(COLOR_BLACK)
        self.draw_text("STARFIELD STORM + Distinct SFX", 50, WIN_WIDTH // 2, WIN_HEIGHT // 2 - 90, COLOR_WHITE)
        self.draw_text("Press [SPACE] to START or [Q] to QUIT", 24, WIN_WIDTH // 2, WIN_HEIGHT // 2 - 40, COLOR_WHITE)
        pygame.display.flip()
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_q):
                self.running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                self.reset_game(); self.state = "GAME"

    def game_over_loop(self):
        self.screen.fill(COLOR_BLACK)
        self.draw_text("GAME OVER", 50, WIN_WIDTH // 2, WIN_HEIGHT // 2 - 50, (255, 0, 0))
        self.draw_text(f"FINAL SCORE: {int(self.score)}", 24, WIN_WIDTH // 2, WIN_HEIGHT // 2, COLOR_WHITE)
        self.draw_text("Press [R] to RESTART or [Q] to QUIT", 24, WIN_WIDTH // 2, WIN_HEIGHT // 2 + 50, COLOR_WHITE)
        pygame.display.flip()
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_q):
                self.running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                self.reset_game(); self.state = "GAME"

    def game_loop(self):
        self.clock.tick(FPS)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False

        self.update_stars()
        self.player.update()
        self.player.shoot(self.bullets)

        elapsed = pygame.time.get_ticks()
        diff = elapsed // config["difficulty"]["time_scale_ms"]
        self.score += 0.03

        if elapsed - self.last_wave >= self.wave_interval:
            self.spawn_enemies(diff)
            self.spawn_obstacles(diff)
            self.spawn_health_pickups()
            self.spawn_powerups()
            self.last_wave = elapsed
            self.wave_interval = max(self.wave_interval_min, self.wave_interval - self.wave_decr)

        # Update bullets
        for b in self.bullets[:]:
            b.update()
            if b.off_screen():
                self.bullets.remove(b)

        # Update enemies separately (requires bullets and player)
        for enemy in self.enemies[:]:
            enemy.update(self.bullets, self.player)
            if enemy.off_screen():
                self.enemies.remove(enemy)

        # Update obstacles, pickups, and powerups (no extra parameters)
        for group in (self.obstacles, self.pickups, self.powerups):
            for obj in group[:]:
                obj.update()
                if obj.off_screen():
                    group.remove(obj)

        self.handle_collisions()

        if self.player.health <= 0:
            if sound_effects.get("player_die"):
                sound_effects["player_die"].play()
            self.state = "GAME_OVER"

        self.draw_game()
        pygame.display.flip()

    def spawn_enemies(self, diff):
        for _ in range(1 + int(diff * config["difficulty"]["enemy_spawn_factor"])):
            x, y = random.randint(20, WIN_WIDTH - 20), -30
            speed = config["enemy"]["base_speed"] + diff * 0.05
            self.enemies.append(Enemy(x, y, speed, diff))

    def spawn_obstacles(self, diff):
        for _ in range(max(1, int(diff // config["difficulty"]["obstacle_spawn_factor"]))):
            self.obstacles.append(Obstacle())

    def spawn_health_pickups(self):
        if random.random() < config["difficulty"]["pickup_chance"]:
            self.pickups.append(HealthPickup())

    def spawn_powerups(self):
        for ptype, info in config.get("powerups", {}).items():
            if ptype == "rarities": continue
            if random.random() < info.get("spawn_chance", 0.0):
                self.powerups.append(Powerup(ptype))

    def handle_collisions(self):
        bconf = config["bullet"]
        enemy_damage = bconf["enemy_bullet_damage"]
        # Player bullets vs Enemies/Obstacles
        for b in self.bullets[:]:
            if b.from_player:
                for group in (self.enemies, self.obstacles):
                    for obj in group[:]:
                        if math.hypot(b.x - obj.x, b.y - obj.y) < (b.radius + obj.radius):
                            obj.health -= 1
                            if sound_effects.get("enemy_hit") and group == self.enemies:
                                sound_effects["enemy_hit"].play()
                            if obj.health <= 0:
                                if sound_effects.get("enemy_die"):
                                    sound_effects["enemy_die"].play()
                                group.remove(obj); self.score += 10
                            if b in self.bullets:
                                self.bullets.remove(b)
                            break
            else:
                if math.hypot(b.x - self.player.x, b.y - self.player.y) < (b.radius + self.player.radius):
                    if not self.player.is_shielded():
                        if sound_effects.get("player_hit"):
                            sound_effects["player_hit"].play()
                        self.player.health -= enemy_damage
                    if b in self.bullets:
                        self.bullets.remove(b)
        # Obstacles and Enemies colliding with Player
        for obj, dmg_attr in ((self.obstacles, "collision_damage"), (self.enemies, "collision_damage")):
            for o in obj[:]:
                if math.hypot(o.x - self.player.x, o.y - self.player.y) < (o.radius + self.player.radius):
                    if not self.player.is_shielded():
                        if sound_effects.get("obstacle_hit_player"):
                            sound_effects["obstacle_hit_player"].play()
                        self.player.health -= getattr(o, "collision_damage", self.player.collision_damage)
                    if o in obj:
                        obj.remove(o)
        # Health pickups vs Player
        for p in self.pickups[:]:
            if math.hypot(p.x - self.player.x, p.y - self.player.y) < (p.radius + self.player.radius):
                self.player.health = min(self.player.health + p.restore, config["player"]["initial_health"])
                self.pickups.remove(p)
        # Powerups vs Player
        for pw in self.powerups[:]:
            if math.hypot(pw.x - self.player.x, pw.y - self.player.y) < (pw.radius + self.player.radius):
                self.player.apply_powerup(pw.ptype, pw.duration)
                if sound_effects.get(f"powerup_{pw.ptype}"):
                    sound_effects[f"powerup_{pw.ptype}"].play()
                if pw.ptype == "nuke":
                    for e in self.enemies:
                        if sound_effects.get("enemy_die"):
                            sound_effects["enemy_die"].play()
                        self.score += 10
                    self.enemies.clear(); self.obstacles.clear()
                self.powerups.remove(pw)

    def update_stars(self):
        self.stars = [(sx, sy + 2 if sy + 2 <= WIN_HEIGHT else 0) for sx, sy in self.stars]

    def draw_game(self):
        self.screen.fill(COLOR_BLACK)
        for sx, sy in self.stars:
            pygame.draw.circle(self.screen, COLOR_WHITE, (sx, sy), 2)
        # Gather and sort objects by their z_order
        objects = [(self.player.z_order, self.player)]
        for group in (self.bullets, self.enemies, self.obstacles, self.pickups, self.powerups):
            objects.extend((obj.z_order, obj) for obj in group)
        for _, obj in sorted(objects, key=lambda x: x[0]):
            obj.draw(self.screen)
        self.draw_text(f"Score: {int(self.score)}", 24, 50, 20, COLOR_WHITE, "left")
        self.draw_text(f"Health: {self.player.health}", 24, WIN_WIDTH - 150, 20, COLOR_WHITE, "left")

    def draw_text(self, text, size, x, y, color, align="center"):
        font = pygame.font.SysFont(None, size)
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=(x, y)) if align == "center" else surface.get_rect(topleft=(x, y))
        self.screen.blit(surface, rect)

def main():
    Game().run()

if __name__ == "__main__":
    main()
