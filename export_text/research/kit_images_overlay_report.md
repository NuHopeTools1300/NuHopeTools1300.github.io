# Kit Images Overlay Extraction

This pass extracts kit-name overlays from `Kit_images.pptx`, keeps the green/yellow label distinction from the deck, and cross-matches reused embedded photos against the earlier `ILM75-77_timeline_.pptx` media set.

## Summary

- Slides parsed: `44`
- Overlay labels extracted: `529`
- Green labels (`identified_in_this_image`): `204`
- Yellow labels (`identified_elsewhere`): `302`
- Slides with an exact reused timeline image: `30` of `44`
- Slides reusing the same embedded image for full view plus zoom crop: `24` of `44`
- Labels mapped with high-confidence exact reused-image linkage: `432`

## Notes

- Text color was not the useful signal here; the slide shape line color carries the green/yellow meaning.
- `projected_x_in_original` and `projected_y_in_original` are normalized coordinates in the underlying original image space.
- When a slide reuses the same embedded photo for both the main image and a zoom crop, those projected coordinates are especially useful because they land back on the larger original cleanly.
- Some slides contain media that are not exact file matches to the earlier timeline deck. Those remain useful locally, but their cross-deck linkage is lower confidence until image-level matching is added.

## Top Overlay-Dense Slides

- Slide `33` `ILM_Shop_Image`: `54` green, `15` yellow, base media `image50.jpg` -> timeline `image32.jpg`
- Slide `30` `Blockade_Runner`: `25` green, `14` yellow, base media `image45.jpg` -> timeline `image17.jpg`
- Slide `35` `ILM_KITS`: `22` green, `16` yellow, base media `image43.jpg` -> timeline `image27.jpg`
- Slide `40` `Blockade_Runner_02`: `3` green, `29` yellow, base media `image40.jpg` -> timeline `image11.jpg`
- Slide `19` `Star_Destroyer_right`: `1` green, `26` yellow, base media `image18.jpg` -> timeline `image44.jpg`
- Slide `18` `Star_Destroyer_workbench`: `22` green, `3` yellow, base media `image10.jpg` -> timeline `image29.jpg`
- Slide `36` `Tile`: `12` green, `9` yellow, base media `image38.jpg` -> timeline `image31.jpg`
- Slide `22` `X_03`: `3` green, `16` yellow, base media `image19.jpg` -> timeline `none`

## Unmatched Slide Bases

- Slide `3` `Pirateship_02` uses base media `image16.jpg` with no exact cross-deck file match yet
- Slide `8` `Xwing_back_2` uses base media `image7.jpg` with no exact cross-deck file match yet
- Slide `9` `Landspeeder_02` uses base media `image17.jpg` with no exact cross-deck file match yet
- Slide `10` `Landspeeder_03` uses base media `image13.jpg` with no exact cross-deck file match yet
- Slide `11` `Landspeeder_04` uses base media `image23.jpg` with no exact cross-deck file match yet
- Slide `13` `Sandcrawler_right` uses base media `image8.jpg` with no exact cross-deck file match yet
- Slide `17` `????` uses base media `image25.png` with no exact cross-deck file match yet
- Slide `22` `X_03` uses base media `image19.jpg` with no exact cross-deck file match yet
- Slide `23` `X_03` uses base media `image24.jpg` with no exact cross-deck file match yet
- Slide `25` `Fleet` uses base media `image32.jpg` with no exact cross-deck file match yet
- Slide `42` `Erland_Y` uses base media `image51.jpg` with no exact cross-deck file match yet
- Slide `43` `TIE_bench` uses base media `image48.jpg` with no exact cross-deck file match yet
