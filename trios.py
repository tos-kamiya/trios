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

import pygame
import random
import sys
from typing import List, Optional, Tuple

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
GAP_FILL_COLOR: Tuple[int, int, int] = (160, 160, 160)      # Gap fill color

# --- Pastel Piece Colors ---
PASTEL_CYAN: Tuple[int, int, int] = (100, 240, 255)
PASTEL_MAGENTA: Tuple[int, int, int] = (255, 100, 150)
PASTEL_ORANGE: Tuple[int, int, int] = (255, 160, 60)
PASTEL_GREEN: Tuple[int, int, int] = (100, 255, 100)
PASTEL_BLUE: Tuple[int, int, int] = (70, 150, 230)
PASTEL_YELLOW: Tuple[int, int, int] = (255, 230, 0)

# --- Triomino Shape Definitions ---
# Each shape is defined as (name, [relative positions], color).
# The relative positions are defined with respect to the pivot (0,0).
shapes: List[Tuple[str, List[Tuple[int, int]], Tuple[int, int, int]]] = [
    ("I",       [(-1, 0), (0, 0), (1, 0)], PASTEL_CYAN),
    ("slash",   [(-1, -1), (0, 0), (1, 1)], PASTEL_MAGENTA),
    ("L",       [(0, -1), (0, 0), (1, 0)], PASTEL_ORANGE),
    ("small_r", [(-1, 0), (0, 0), (1, 1)], PASTEL_GREEN),
    ("mirror_r",[ (1, 0), (0, 0), (-1, 1)], PASTEL_BLUE),
    ("v",       [(-1, 0), (1, 0), (0, 1)], PASTEL_YELLOW)
]
# Weighting for appearance: "slash" and "v" get lower weight
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

# --- Drawing Functions ---
def draw_grid(surface: pygame.Surface, grid: List[List[Optional[Tuple[int, int, int]]]]) -> None:
    """
    Draw the game grid along with fixed blocks. For each column, determine the topmost fixed block 
    (ignoring falling pieces), and then fill every empty cell below that position with GAP_FILL_COLOR 
    to indicate a gap.

    Args:
        surface (pygame.Surface): The drawing surface.
        grid (List[List[Optional[Tuple[int, int, int]]]]): The game grid.
    """
    # For each column, compute the topmost fixed cell (if any) in the visible area.
    top_filled_by_column: List[Optional[int]] = [None] * GRID_WIDTH
    for x in range(GRID_WIDTH):
        for y in range(VISIBLE_ROW_OFFSET, GRID_HEIGHT):
            if grid[y][x] is not None:
                top_filled_by_column[x] = y
                break

    # Draw each cell in the visible area.
    for y in range(VISIBLE_ROW_OFFSET, GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            rect = pygame.Rect(x * BLOCK_SIZE, (y - VISIBLE_ROW_OFFSET) * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
            if grid[y][x] is not None:
                # Draw the fixed block.
                pygame.draw.rect(surface, grid[y][x], rect)
            else:
                # If there is a fixed block in this column and this row is below (or equal to) that topmost fixed block, fill the gap.
                if top_filled_by_column[x] is not None and y >= top_filled_by_column[x]:
                    pygame.draw.rect(surface, GAP_FILL_COLOR, rect)
            pygame.draw.rect(surface, GRID_LINE_COLOR, rect, 1)

def draw_piece(surface: pygame.Surface, piece: Piece) -> None:
    """
    Draw the active (falling) piece on the surface.

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
        box_rect (pygame.Rect): The rectangle defining the preview area.
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
    Draw the next two pieces in preview boxes on the right side of the window.

    Args:
        surface (pygame.Surface): The drawing surface.
        next_piece (Piece): The next piece.
        next_next_piece (Piece): The piece following the next.
    """
    preview_x = WINDOW_WIDTH + PREVIEW_MARGIN

    # Upper preview box shows next_next_piece.
    box1_rect = pygame.Rect(preview_x, PREVIEW_MARGIN, PREVIEW_BOX_WIDTH, PREVIEW_BOX_HEIGHT)
    draw_preview_box(surface, next_next_piece, box1_rect)
    # Lower preview box shows next_piece.
    box2_rect = pygame.Rect(preview_x, PREVIEW_MARGIN + PREVIEW_BOX_HEIGHT + PREVIEW_MARGIN, PREVIEW_BOX_WIDTH, PREVIEW_BOX_HEIGHT)
    draw_preview_box(surface, next_piece, box2_rect)
    # Draw an outer border around the preview area.
    box_rect = pygame.Rect(preview_x, PREVIEW_MARGIN, PREVIEW_BOX_WIDTH, PREVIEW_BOX_HEIGHT * 2 + PREVIEW_MARGIN)
    pygame.draw.rect(surface, STAGE_BORDER_COLOR, box_rect, 2)

def draw_info(surface: pygame.Surface, score: int, stage: int, lines_to_clear: int) -> None:
    """
    Draw the game information (score, stage, and lines remaining) on the right side.

    Args:
        surface (pygame.Surface): The drawing surface.
        score (int): The current score.
        stage (int): The current stage.
        lines_to_clear (int): The number of lines remaining to clear for stage advancement.
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

def draw_pause_message(surface: pygame.Surface) -> None:
    """
    Draw a "Paused" message in the center of the screen.

    Args:
        surface (pygame.Surface): The drawing surface.
    """
    font = pygame.font.SysFont(None, 72)
    text = font.render("Paused", True, TEXT_COLOR)
    rect = text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
    surface.blit(text, rect)

# --- Main Game Loop ---
def main() -> None:
    """
    Main function to run the TRIOS game.
    """
    pygame.init()
    screen: pygame.Surface = pygame.display.set_mode((WINDOW_WIDTH_EXTENDED, WINDOW_HEIGHT))
    pygame.display.set_caption("TRIOS")
    clock: pygame.time.Clock = pygame.time.Clock()

    grid: List[List[Optional[Tuple[int, int, int]]]] = create_grid()

    # Stage management
    stage: int = 1
    stage_threshold: int = stage * STAGE_CLEAR_FACTOR  # e.g., Stage 1: 10 lines, Stage 2: 20 lines, etc.
    lines_cleared_stage: int = 0  # Lines cleared in the current stage

    # Set initial fall delay based on stage and start fall timer event
    fall_delay: int = get_initial_fall_delay(stage)
    fall_event: int = pygame.USEREVENT + 1
    pygame.time.set_timer(fall_event, fall_delay)

    # Score and combo multiplier
    score: int = 0
    combo_multiplier: int = 1

    # Generate the first two preview pieces
    effective_weights: List[int] = [max(w - (stage - 1), 5) for w in base_shape_weights]
    next_piece: Piece = Piece(random.choices(shapes, weights=effective_weights, k=1)[0], GRID_WIDTH // 2, 1)
    next_next_piece: Piece = Piece(random.choices(shapes, weights=effective_weights, k=1)[0], GRID_WIDTH // 2, 1)
    # Set current piece from next_piece
    current_piece: Piece = next_piece
    current_piece.x = GRID_WIDTH // 2
    current_piece.y = 1
    # Update preview: next_piece becomes next_next_piece, then generate a new next_next_piece
    next_piece = next_next_piece
    next_next_piece = Piece(random.choices(shapes, weights=effective_weights, k=1)[0], GRID_WIDTH // 2, 1)

    paused: bool = False  # Pause flag

    running: bool = True
    while running:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p:
                    paused = not paused
                elif event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                    running = False

                if paused:
                    continue

                if event.key == pygame.K_LEFT:
                    new_positions = [(x - 1, y) for (x, y) in current_piece.get_block_positions()]
                    if valid_position(current_piece, grid, new_positions):
                        current_piece.x -= 1
                elif event.key == pygame.K_RIGHT:
                    new_positions = [(x + 1, y) for (x, y) in current_piece.get_block_positions()]
                    if valid_position(current_piece, grid, new_positions):
                        current_piece.x += 1
                elif event.key == pygame.K_DOWN:
                    new_positions = [(x, y + 1) for (x, y) in current_piece.get_block_positions()]
                    if valid_position(current_piece, grid, new_positions):
                        current_piece.y += 1
                elif event.key == pygame.K_UP:
                    new_blocks = current_piece.rotate()
                    rotated_positions = [(current_piece.x + bx, current_piece.y + by) for (bx, by) in new_blocks]
                    if valid_position(current_piece, grid, rotated_positions):
                        current_piece.apply_rotation(new_blocks)
                elif event.key == pygame.K_SPACE:
                    while valid_position(current_piece, grid):
                        current_piece.y += 1
                    current_piece.y -= 1
                    add_piece_to_grid(current_piece, grid)
                    grid, lines_cleared = clear_full_lines(grid)
                    if lines_cleared > 0:
                        score += (lines_cleared ** 2) * combo_multiplier
                        combo_multiplier *= 2
                        lines_cleared_stage += lines_cleared
                    else:
                        combo_multiplier = 1

                    fall_delay = max(MIN_FALL_DELAY, fall_delay - 2)
                    pygame.time.set_timer(fall_event, fall_delay)

                    if lines_cleared_stage >= stage_threshold:
                        grid = create_grid()  # Clear the field
                        lines_cleared_stage -= stage_threshold
                        stage += 1
                        stage_threshold = stage * STAGE_CLEAR_FACTOR
                        fall_delay = get_initial_fall_delay(stage)
                        pygame.time.set_timer(fall_event, fall_delay)

                    current_piece = next_piece
                    current_piece.x = GRID_WIDTH // 2
                    current_piece.y = 1
                    effective_weights: List[int] = [max(w - (stage - 1), 5) for w in base_shape_weights]
                    next_piece = next_next_piece
                    next_next_piece = Piece(random.choices(shapes, weights=effective_weights, k=1)[0], GRID_WIDTH // 2, 1)
                    if not valid_position(current_piece, grid):
                        print("Game Over. Final Score:", score)
                        running = False

            elif event.type == fall_event and not paused:
                new_y = current_piece.y + 1
                new_positions = [(x, y + 1) for (x, y) in current_piece.get_block_positions()]
                if valid_position(current_piece, grid, new_positions):
                    current_piece.y = new_y
                else:
                    add_piece_to_grid(current_piece, grid)
                    grid, lines_cleared = clear_full_lines(grid)
                    if lines_cleared > 0:
                        score += (lines_cleared ** 2) * combo_multiplier
                        combo_multiplier *= 2
                        lines_cleared_stage += lines_cleared
                    else:
                        combo_multiplier = 1

                    fall_delay = max(MIN_FALL_DELAY, fall_delay - 2)
                    pygame.time.set_timer(fall_event, fall_delay)

                    if lines_cleared_stage >= stage_threshold:
                        grid = create_grid()  # Clear the field on stage clear
                        lines_cleared_stage -= stage_threshold
                        stage += 1
                        stage_threshold = stage * STAGE_CLEAR_FACTOR
                        fall_delay = get_initial_fall_delay(stage)
                        pygame.time.set_timer(fall_event, fall_delay)

                    current_piece = next_piece
                    current_piece.x = GRID_WIDTH // 2
                    current_piece.y = 1
                    effective_weights: List[int] = [max(w - (stage - 1), 5) for w in base_shape_weights]
                    next_piece = next_next_piece
                    next_next_piece = Piece(random.choices(shapes, weights=effective_weights, k=1)[0], GRID_WIDTH // 2, 1)
                    if not valid_position(current_piece, grid):
                        print("Game Over. Final Score:", score)
                        running = False

        screen.fill(BG_COLOR)
        draw_grid(screen, grid)
        draw_piece(screen, current_piece)
        draw_stage_border(screen)
        draw_previews(screen, next_piece, next_next_piece)
        lines_remaining = stage_threshold - lines_cleared_stage
        draw_info(screen, score, stage, lines_remaining)
        if paused:
            draw_pause_message(screen)
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
