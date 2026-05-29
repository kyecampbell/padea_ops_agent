-- Option C: vegetarian-option (VO) fallback — adds variant tracking and flags VO-capable menu items

ALTER TABLE order_lines ADD COLUMN variant text;

ALTER TABLE menu_items ADD COLUMN has_vegetarian_option boolean NOT NULL DEFAULT false;

UPDATE menu_items
SET has_vegetarian_option = true
WHERE id IN (6, 10, 13, 15, 16, 17, 23, 24, 25, 27, 31, 32, 35, 36, 37);
