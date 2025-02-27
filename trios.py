#!/usr/bin/env python3
"""
TRIOS - A Triomino Falling-Block Game

TRIOS is a falling-block puzzle game featuring triomino pieces (three connected squares)
that offers a unique twist on the classic Tetris formula. Pieces fall on an 8×22 grid
(with the top 2 rows hidden), and players clear lines to progress through stages. The game
includes a preview of the next two pieces, dynamic scoring with combo multipliers, and
increasing falling speed.

Author: Toshihiro Kamiya (kamiya@mbj.nifty.com)
"""

from enum import Enum
import random
import sys
from typing import List, Optional, Tuple

import pygame

# --- Constants ---
BLOCK_SIZE: int = 30

# Field size (internal grid has 22 rows; the top 2 rows are hidden)
GRID_WIDTH: int = 8
GRID_HEIGHT: int = 22
VISIBLE_ROW_OFFSET: int = 2  # Number of top rows to hide

# Window size (only the visible part of the grid is displayed)
WINDOW_WIDTH: int = GRID_WIDTH * BLOCK_SIZE
WINDOW_HEIGHT: int = (GRID_HEIGHT - VISIBLE_ROW_OFFSET) * BLOCK_SIZE

FPS: int = 60

# Preview area constants
PREVIEW_MARGIN: int = 20
PREVIEW_BOX_WIDTH: int = 200   # Width of preview boxes
PREVIEW_BOX_HEIGHT: int = 100
PREVIEW_EXTRA: int = 50        # Additional margin on the right

# Extended window width to accommodate the preview area
WINDOW_WIDTH_EXTENDED: int = WINDOW_WIDTH + PREVIEW_MARGIN * 2 + PREVIEW_BOX_WIDTH + PREVIEW_EXTRA

# Falling speed (in milliseconds)
INITIAL_FALL_DELAY: int = 800  # Initial falling delay for Stage 1 (ms)
MIN_FALL_DELAY: int = 100      # Minimum falling delay (ms)

def get_initial_fall_delay(stage: int) -> int:
    """
    Calculate the initial falling delay based on the current stage.

    Args:
        stage (int): The current stage number.

    Returns:
        int: The falling delay in milliseconds.
    """
    return max(800 - (stage - 1) * 50, MIN_FALL_DELAY)

# Stage clear factor: Stage 1 clears 10 lines, Stage 2 clears 20 lines, etc.
STAGE_CLEAR_FACTOR: int = 10

# --- Color Constants ---
BG_COLOR: Tuple[int, int, int] = (250, 250, 250)          # Background
GRID_LINE_COLOR: Tuple[int, int, int] = (200, 200, 200)     # Grid lines
PIECE_BORDER_COLOR: Tuple[int, int, int] = (60, 60, 60)     # Piece borders
TEXT_COLOR: Tuple[int, int, int] = (60, 60, 60)             # Text color
STAGE_BORDER_COLOR: Tuple[int, int, int] = (0, 0, 0)        # Field border
GAP_FILL_COLOR: Tuple[int, int, int] = (90, 90, 90)         # Gap fill color
FALLING_COLUMN_COLOR: Tuple[int, int, int] = (240, 240, 240)

# --- Pastel (Vivid) Piece Colors ---
PASTEL_CYAN: Tuple[int, int, int] = (100, 240, 255)
PASTEL_MAGENTA: Tuple[int, int, int] = (255, 100, 150)
PASTEL_ORANGE: Tuple[int, int, int] = (255, 160, 60)
PASTEL_GREEN: Tuple[int, int, int] = (100, 255, 100)
PASTEL_BLUE: Tuple[int, int, int] = (70, 150, 230)
PASTEL_YELLOW: Tuple[int, int, int] = (255, 230, 0)

# --- Triomino Shape Definitions ---
# Each shape is defined as (name, [relative positions], color).
# Relative positions are with respect to the pivot (0,0).
shapes: List[Tuple[str, List[Tuple[int, int]], Tuple[int, int, int]]] = [
    ("I",       [(-1, 0), (0, 0), (1, 0)], PASTEL_CYAN),
    ("slash",   [(-1, -1), (0, 0), (1, 1)], PASTEL_MAGENTA),
    ("L",       [(0, -1), (0, 0), (1, 0)], PASTEL_ORANGE),
    ("j",       [(0, -1), (0, 0), (-1, 1)], PASTEL_GREEN),
    ("shi",     [(0, -1), (0, 0), (1, 1)], PASTEL_BLUE),
    ("v",       [(-1, 0), (1, 0), (0, 1)], PASTEL_YELLOW)
]
# Base weights for appearance
base_shape_weights: List[int] = [15, 5, 15, 15, 15, 5]

# --- Piece Class ---
class Piece:
    """
    Represents a falling triomino piece.

    Attributes:
        name (str): The name of the piece.
        blocks (List[Tuple[int, int]]): The relative positions of the blocks.
        color (Tuple[int, int, int]): The color of the piece.
        x (int): The x-coordinate of the pivot on the grid.
        y (int): The y-coordinate of the pivot on the grid.
    """
    def __init__(self, shape: Tuple[str, List[Tuple[int, int]], Tuple[int, int, int]], grid_x: int, grid_y: int) -> None:
        self.name: str = shape[0]
        self.blocks: List[Tuple[int, int]] = shape[1][:]
        self.color: Tuple[int, int, int] = shape[2]
        self.x: int = grid_x
        self.y: int = grid_y

    def get_block_positions(self) -> List[Tuple[int, int]]:
        """
        Get the absolute positions of the piece's blocks on the grid.

        Returns:
            List[Tuple[int, int]]: A list of (x, y) positions.
        """
        return [(self.x + bx, self.y + by) for (bx, by) in self.blocks]

    def rotate(self) -> List[Tuple[int, int]]:
        """
        Compute the new relative block positions after a 90° clockwise rotation.

        Returns:
            List[Tuple[int, int]]: The new relative positions.
        """
        return [(by, -bx) for (bx, by) in self.blocks]

    def apply_rotation(self, new_blocks: List[Tuple[int, int]]) -> None:
        """
        Update the piece's block positions after rotation.

        Args:
            new_blocks (List[Tuple[int, int]]): The new relative positions.
        """
        self.blocks = new_blocks

# --- Grid Functions ---
def create_grid() -> List[List[Optional[Tuple[int, int, int]]]]:
    """
    Initialize the game grid.

    Returns:
        List[List[Optional[Tuple[int, int, int]]]]: A 2D grid where each cell is either a color tuple or None.
    """
    return [[None for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]

def valid_position(piece: Piece, grid: List[List[Optional[Tuple[int, int, int]]]],
                   block_positions: Optional[List[Tuple[int, int]]] = None) -> bool:
    """
    Check if the piece's block positions are valid (inside the grid and on empty cells).
    Cells with negative y-values (above the visible area) are ignored.

    Args:
        piece (Piece): The piece to check.
        grid (List[List[Optional[Tuple[int, int, int]]]]): The game grid.
        block_positions (Optional[List[Tuple[int, int]]]): Optional positions to check.

    Returns:
        bool: True if valid, False otherwise.
    """
    if block_positions is None:
        block_positions = piece.get_block_positions()
    for (x, y) in block_positions:
        if x < 0 or x >= GRID_WIDTH:
            return False
        if y >= GRID_HEIGHT:
            return False
        if y >= 0 and grid[y][x] is not None:
            return False
    return True

def add_piece_to_grid(piece: Piece, grid: List[List[Optional[Tuple[int, int, int]]]]) -> None:
    """
    Fix the piece onto the grid.

    Args:
        piece (Piece): The piece to add.
        grid (List[List[Optional[Tuple[int, int, int]]]]): The game grid.
    """
    for (x, y) in piece.get_block_positions():
        if y >= 0:
            grid[y][x] = piece.color

def clear_full_lines(grid: List[List[Optional[Tuple[int, int, int]]]]) -> Tuple[List[List[Optional[Tuple[int, int, int]]]], int]:
    """
    Remove full lines from the grid.

    Args:
        grid (List[List[Optional[Tuple[int, int, int]]]]): The current grid.

    Returns:
        Tuple[List[List[Optional[Tuple[int, int, int]]]], int]: A tuple with the new grid and the number of cleared lines.
    """
    new_grid = [row for row in grid if None in row]
    num_cleared = len(grid) - len(new_grid)
    for _ in range(num_cleared):
        new_grid.insert(0, [None for _ in range(GRID_WIDTH)])
    return new_grid, num_cleared

# --- Game State Enum ---
class GameState(Enum):
    RUNNING = 1       # Normal gameplay
    PAUSED = 2        # Paused by player
    STAGE_CLEAR = 3   # Stage clear pause (waiting for any key)
    GAME_OVER = 4     # Game over state

# --- Game Context Class ---
class GameContext:
    """
    Holds all game state data.
    """
    def __init__(self) -> None:
        self.grid: List[List[Optional[Tuple[int, int, int]]]] = create_grid()
        self.stage: int = 1
        self.stage_threshold: int = self.stage * STAGE_CLEAR_FACTOR
        self.lines_cleared_stage: int = 0
        self.fall_delay: int = get_initial_fall_delay(self.stage)
        self.score: int = 0
        self.combo_multiplier: int = 1
        self.state: GameState = GameState.RUNNING
        self.close_request: bool = False
        # Initialize preview pieces using effective weights
        effective_weights: List[int] = [max(w - (self.stage - 1), 5) for w in base_shape_weights]
        self.next_piece: Piece = Piece(random.choices(shapes, weights=effective_weights, k=1)[0], GRID_WIDTH // 2, 1)
        self.next_next_piece: Piece = Piece(random.choices(shapes, weights=effective_weights, k=1)[0], GRID_WIDTH // 2, 1)
        self.current_piece: Piece = self.next_piece
        self.current_piece.x = GRID_WIDTH // 2
        self.current_piece.y = 1
        self.next_piece = self.next_next_piece
        self.next_next_piece = Piece(random.choices(shapes, weights=effective_weights, k=1)[0], GRID_WIDTH // 2, 1)

# --- Drawing Functions ---
def draw_grid(surface: pygame.Surface, grid: List[List[Optional[Tuple[int, int, int]]]], 
              falling_columns: Optional[set[int]] = None) -> None:
    """
    Draw the game grid along with fixed blocks.
    For each column, find the topmost fixed cell (within the visible area).
    Then, for each empty cell:
      - If below (or equal to) that cell, fill with GAP_FILL_COLOR.
      - Else if the column is in falling_columns, fill with FALLING_COLUMN_COLOR.
    Draw grid lines over the cells.
    """
    top_filled_by_column: List[Optional[int]] = [None] * GRID_WIDTH
    for x in range(GRID_WIDTH):
        for y in range(VISIBLE_ROW_OFFSET, GRID_HEIGHT):
            if grid[y][x] is not None:
                top_filled_by_column[x] = y
                break

    for y in range(VISIBLE_ROW_OFFSET, GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            rect = pygame.Rect(x * BLOCK_SIZE, (y - VISIBLE_ROW_OFFSET) * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
            if grid[y][x] is not None:
                pygame.draw.rect(surface, grid[y][x], rect)
            else:
                if top_filled_by_column[x] is not None and y >= top_filled_by_column[x]:
                    pygame.draw.rect(surface, GAP_FILL_COLOR, rect)
                elif falling_columns is not None and x in falling_columns:
                    pygame.draw.rect(surface, FALLING_COLUMN_COLOR, rect)
            pygame.draw.rect(surface, GRID_LINE_COLOR, rect, 1)

def draw_piece(surface: pygame.Surface, piece: Piece) -> None:
    """
    Draw the active (falling) piece.
    
    Args:
        surface (pygame.Surface): The drawing surface.
        piece (Piece): The active piece.
    """
    for (x, y) in piece.get_block_positions():
        if y >= VISIBLE_ROW_OFFSET:
            rect = pygame.Rect(x * BLOCK_SIZE, (y - VISIBLE_ROW_OFFSET) * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
            pygame.draw.rect(surface, piece.color, rect)
            pygame.draw.rect(surface, PIECE_BORDER_COLOR, rect, 1)

def draw_stage_border(surface: pygame.Surface) -> None:
    """
    Draw a border around the visible game field.
    
    Args:
        surface (pygame.Surface): The drawing surface.
    """
    border_rect = pygame.Rect(0, 0, GRID_WIDTH * BLOCK_SIZE, (GRID_HEIGHT - VISIBLE_ROW_OFFSET) * BLOCK_SIZE)
    pygame.draw.rect(surface, STAGE_BORDER_COLOR, border_rect, 2)

def draw_preview_box(surface: pygame.Surface, piece: Piece, box_rect: pygame.Rect) -> None:
    """
    Draw a preview of a piece within a specified rectangle.
    
    Args:
        surface (pygame.Surface): The drawing surface.
        piece (Piece): The piece to preview.
        box_rect (pygame.Rect): The preview area.
    """
    center_x = box_rect.x + box_rect.width // 2
    center_y = box_rect.y + box_rect.height // 2
    for (bx, by) in piece.blocks:
        block_x = center_x + bx * BLOCK_SIZE - BLOCK_SIZE // 2
        block_y = center_y + by * BLOCK_SIZE - BLOCK_SIZE // 2
        block_rect = pygame.Rect(block_x, block_y, BLOCK_SIZE, BLOCK_SIZE)
        pygame.draw.rect(surface, piece.color, block_rect)
        pygame.draw.rect(surface, PIECE_BORDER_COLOR, block_rect, 1)

def draw_previews(surface: pygame.Surface, next_piece: Piece, next_next_piece: Piece) -> None:
    """
    Draw the next two pieces in preview boxes on the right side.
    
    Args:
        surface (pygame.Surface): The drawing surface.
        next_piece (Piece): The next piece.
        next_next_piece (Piece): The piece following the next.
    """
    preview_x = WINDOW_WIDTH + PREVIEW_MARGIN
    box1_rect = pygame.Rect(preview_x, PREVIEW_MARGIN, PREVIEW_BOX_WIDTH, PREVIEW_BOX_HEIGHT)
    draw_preview_box(surface, next_next_piece, box1_rect)
    box2_rect = pygame.Rect(preview_x, PREVIEW_MARGIN + PREVIEW_BOX_HEIGHT + PREVIEW_MARGIN, PREVIEW_BOX_WIDTH, PREVIEW_BOX_HEIGHT)
    draw_preview_box(surface, next_piece, box2_rect)
    box_rect = pygame.Rect(preview_x, PREVIEW_MARGIN, PREVIEW_BOX_WIDTH, PREVIEW_BOX_HEIGHT * 2 + PREVIEW_MARGIN)
    pygame.draw.rect(surface, STAGE_BORDER_COLOR, box_rect, 2)

def draw_info(surface: pygame.Surface, score: int, stage: int, lines_to_clear: int) -> None:
    """
    Draw game information (score, stage, and lines remaining) on the right side.
    
    Args:
        surface (pygame.Surface): The drawing surface.
        score (int): The current score.
        stage (int): The current stage.
        lines_to_clear (int): The number of lines remaining for stage advancement.
    """
    font = pygame.font.SysFont(None, 36)
    text_score = font.render("Score: " + str(score), True, TEXT_COLOR)
    text_stage = font.render("Stage: " + str(stage), True, TEXT_COLOR)
    text_remaining = font.render("Lines remaining: " + str(lines_to_clear), True, TEXT_COLOR)
    text_x = WINDOW_WIDTH + PREVIEW_MARGIN
    text_y = PREVIEW_MARGIN + 2 * (PREVIEW_BOX_HEIGHT + PREVIEW_MARGIN)
    surface.blit(text_score, (text_x, text_y))
    surface.blit(text_stage, (text_x, text_y + 40))
    surface.blit(text_remaining, (text_x, text_y + 80))

def draw_pause_message(surface: pygame.Surface, message: str = "Paused") -> None:
    """
    Draw a multi-line message at the center of the screen.
    
    Args:
        surface (pygame.Surface): The drawing surface.
        message (str): The message to display (use '\n' for line breaks).
    """
    font = pygame.font.SysFont(None, 42)
    lines = message.split("\n")
    line_heights = [font.size(line)[1] for line in lines]
    total_height = sum(line_heights)
    current_y = (WINDOW_HEIGHT - total_height) // 2
    for i, line in enumerate(lines):
        text_surface = font.render(line, True, TEXT_COLOR)
        text_rect = text_surface.get_rect(center=(WINDOW_WIDTH // 2, current_y + line_heights[i] // 2))
        surface.blit(text_surface, text_rect)
        current_y += line_heights[i]

# --- Main Game Loop Functions ---
class GameContext:
    """
    Encapsulates the overall game state.
    """
    def __init__(self) -> None:
        self.grid: List[List[Optional[Tuple[int, int, int]]]] = create_grid()
        self.stage: int = 1
        self.stage_threshold: int = self.stage * STAGE_CLEAR_FACTOR
        self.lines_cleared_stage: int = 0
        self.fall_delay: int = get_initial_fall_delay(self.stage)
        self.score: int = 0
        self.combo_multiplier: int = 1
        self.state: GameState = GameState.RUNNING
        self.close_request: bool = False
        effective_weights: List[int] = [max(w - (self.stage - 1), 5) for w in base_shape_weights]
        self.next_piece: Piece = Piece(random.choices(shapes, weights=effective_weights, k=1)[0], GRID_WIDTH // 2, 1)
        self.next_next_piece: Piece = Piece(random.choices(shapes, weights=effective_weights, k=1)[0], GRID_WIDTH // 2, 1)
        self.current_piece: Piece = self.next_piece
        self.current_piece.x = GRID_WIDTH // 2
        self.current_piece.y = 1
        self.next_piece = self.next_next_piece
        self.next_next_piece = Piece(random.choices(shapes, weights=effective_weights, k=1)[0], GRID_WIDTH // 2, 1)

def handle_events(ctx: GameContext, fall_event: int) -> None:
    """
    Process user events and update the game context accordingly.
    
    Args:
        ctx (GameContext): The game context.
        fall_event (int): The fall event ID.
    """
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            ctx.close_request = True
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_q, pygame.K_ESCAPE):
                ctx.close_request = True
                continue

            # If game over, ignore all key inputs except for quit.
            if ctx.state == GameState.GAME_OVER:
                continue
            # If paused or stage clear, any key resumes running.
            elif ctx.state in (GameState.PAUSED, GameState.STAGE_CLEAR):
                ctx.state = GameState.RUNNING
                continue

            # At this point, state must be RUNNING.
            assert ctx.state == GameState.RUNNING

            if event.key == pygame.K_p:
                ctx.state = GameState.PAUSED
                continue

            if event.key == pygame.K_LEFT:
                new_positions = [(x - 1, y) for (x, y) in ctx.current_piece.get_block_positions()]
                if valid_position(ctx.current_piece, ctx.grid, new_positions):
                    ctx.current_piece.x -= 1
            elif event.key == pygame.K_RIGHT:
                new_positions = [(x + 1, y) for (x, y) in ctx.current_piece.get_block_positions()]
                if valid_position(ctx.current_piece, ctx.grid, new_positions):
                    ctx.current_piece.x += 1
            elif event.key == pygame.K_DOWN:
                new_positions = [(x, y + 1) for (x, y) in ctx.current_piece.get_block_positions()]
                if valid_position(ctx.current_piece, ctx.grid, new_positions):
                    ctx.current_piece.y += 1
            elif event.key == pygame.K_UP:
                new_blocks = ctx.current_piece.rotate()
                rotated_positions = [(ctx.current_piece.x + bx, ctx.current_piece.y + by) for (bx, by) in new_blocks]
                if valid_position(ctx.current_piece, ctx.grid, rotated_positions):
                    ctx.current_piece.apply_rotation(new_blocks)
            elif event.key == pygame.K_SPACE:
                # Hard drop
                while valid_position(ctx.current_piece, ctx.grid):
                    ctx.current_piece.y += 1
                ctx.current_piece.y -= 1
                add_piece_to_grid(ctx.current_piece, ctx.grid)
                new_grid, lines_cleared = clear_full_lines(ctx.grid)
                ctx.grid = new_grid
                if lines_cleared > 0:
                    ctx.score += (lines_cleared ** 2) * ctx.combo_multiplier
                    ctx.combo_multiplier *= 2
                    ctx.lines_cleared_stage += lines_cleared
                else:
                    ctx.combo_multiplier = 1

                ctx.fall_delay = max(MIN_FALL_DELAY, ctx.fall_delay - 2)
                pygame.time.set_timer(fall_event, ctx.fall_delay)

                if ctx.lines_cleared_stage >= ctx.stage_threshold:
                    ctx.grid = create_grid()  # Clear the field
                    ctx.lines_cleared_stage -= ctx.stage_threshold
                    ctx.stage += 1
                    ctx.stage_threshold = ctx.stage * STAGE_CLEAR_FACTOR
                    ctx.fall_delay = get_initial_fall_delay(ctx.stage)
                    pygame.time.set_timer(fall_event, ctx.fall_delay)
                    ctx.state = GameState.STAGE_CLEAR

                # Set next piece
                ctx.current_piece = ctx.next_piece
                ctx.current_piece.x = GRID_WIDTH // 2
                ctx.current_piece.y = 1
                effective_weights: List[int] = [max(w - (ctx.stage - 1), 5) for w in base_shape_weights]
                ctx.next_piece = ctx.next_next_piece
                ctx.next_next_piece = Piece(random.choices(shapes, weights=effective_weights, k=1)[0], GRID_WIDTH // 2, 1)
                if not valid_position(ctx.current_piece, ctx.grid):
                    print("Game Over. Final Score:", ctx.score)
                    ctx.state = GameState.GAME_OVER

        elif event.type == fall_event and ctx.state == GameState.RUNNING:
            update_fall(ctx, fall_event)

def update_fall(ctx: GameContext, fall_event: int) -> None:
    """
    Process a fall event for the active piece.

    Args:
        ctx (GameContext): The game context.
        fall_event (int): The fall event ID.
    """
    new_y = ctx.current_piece.y + 1
    new_positions = [(x, y + 1) for (x, y) in ctx.current_piece.get_block_positions()]
    if valid_position(ctx.current_piece, ctx.grid, new_positions):
        ctx.current_piece.y = new_y
    else:
        add_piece_to_grid(ctx.current_piece, ctx.grid)
        new_grid, lines_cleared = clear_full_lines(ctx.grid)
        ctx.grid = new_grid
        if lines_cleared > 0:
            ctx.score += (lines_cleared ** 2) * ctx.combo_multiplier
            ctx.combo_multiplier *= 2
            ctx.lines_cleared_stage += lines_cleared
        else:
            ctx.combo_multiplier = 1

        ctx.fall_delay = max(MIN_FALL_DELAY, ctx.fall_delay - 2)
        pygame.time.set_timer(fall_event, ctx.fall_delay)

        if ctx.lines_cleared_stage >= ctx.stage_threshold:
            ctx.grid = create_grid()  # Clear the field on stage clear
            ctx.lines_cleared_stage -= ctx.stage_threshold
            ctx.stage += 1
            ctx.stage_threshold = ctx.stage * STAGE_CLEAR_FACTOR
            ctx.fall_delay = get_initial_fall_delay(ctx.stage)
            pygame.time.set_timer(fall_event, ctx.fall_delay)
            ctx.state = GameState.STAGE_CLEAR

        ctx.current_piece = ctx.next_piece
        ctx.current_piece.x = GRID_WIDTH // 2
        ctx.current_piece.y = 1
        effective_weights: List[int] = [max(w - (ctx.stage - 1), 5) for w in base_shape_weights]
        ctx.next_piece = ctx.next_next_piece
        ctx.next_next_piece = Piece(random.choices(shapes, weights=effective_weights, k=1)[0], GRID_WIDTH // 2, 1)
        if not valid_position(ctx.current_piece, ctx.grid):
            print("Game Over. Final Score:", ctx.score)
            ctx.state = GameState.GAME_OVER

def render_screen(ctx: GameContext, screen: pygame.Surface) -> None:
    """
    Render the game screen.
    
    Args:
        ctx (GameContext): The game context.
        screen (pygame.Surface): The drawing surface.
    """
    screen.fill(BG_COLOR)
    falling_columns: set[int] = { x for (x, _) in ctx.current_piece.get_block_positions() }
    draw_grid(screen, ctx.grid, falling_columns)
    draw_piece(screen, ctx.current_piece)
    draw_stage_border(screen)
    draw_previews(screen, ctx.next_piece, ctx.next_next_piece)
    lines_remaining: int = ctx.stage_threshold - ctx.lines_cleared_stage
    draw_info(screen, ctx.score, ctx.stage, lines_remaining)
    if ctx.state == GameState.PAUSED:
        draw_pause_message(screen)
    elif ctx.state == GameState.STAGE_CLEAR:
        draw_pause_message(screen, message=f"Stage {ctx.stage-1} Clear!\nPress any key\nto continue.")
    elif ctx.state == GameState.GAME_OVER:
        draw_pause_message(screen, message=f"Game Over.\nFinal Score: {ctx.score}\nPress ESC to exit.")
    pygame.display.flip()

def main() -> None:
    """
    Main function to run the TRIOS game.
    """
    pygame.init()
    screen: pygame.Surface = pygame.display.set_mode((WINDOW_WIDTH_EXTENDED, WINDOW_HEIGHT))
    pygame.display.set_caption("TRIOS")
    clock: pygame.time.Clock = pygame.time.Clock()
    
    # Create a fall event timer ID.
    fall_event: int = pygame.USEREVENT + 1
    
    # Initialize game context.
    ctx = GameContext()
    pygame.time.set_timer(fall_event, ctx.fall_delay)
    
    while not ctx.close_request:
        clock.tick(FPS)
        handle_events(ctx, fall_event)
        # Note: update_fall is handled in handle_events for fall_event
        render_screen(ctx, screen)
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
