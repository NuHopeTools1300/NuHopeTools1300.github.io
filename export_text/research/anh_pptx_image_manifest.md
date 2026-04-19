# ANH PPTX Image Manifest - First Pass

## Scope

- Source file: `ILM75-77_timeline_.pptx`
- Source extraction path: `research/_pptx_extract/ppt/media`
- Purpose: connect the slide images to the ANH research timeline, model programs, and later HTML integration

## Related Repo

- Repo path: `C:\Users\gunkel\git_nht\NuHopeTools1300.github.io`
- Repo purpose, per its `README`: an `ILM Van Nuys Kit-Bash Research Platform`
- Why that matters here:
  - this image manifest can become structured `images` data instead of staying a standalone note
  - the current timeline work lines up naturally with the repo's `models`, `images`, `image_links`, and `contributors` concepts

## Working Rule

- `Reviewed` means I visually inspected the image in this pass.
- `Nearest slide anchor` uses the rough left-to-right markers embedded in your PowerPoint timeline:
  - `Sep 1975`
  - `Jan 1976`
  - `Apr 1976`
  - `Jul 1976`
  - `Late 1976 / early 1977`
- `Likely date window` is a research hypothesis, not a claim that the photo itself is securely dated.

## Reviewed Images

| PPTX order | File | Reviewed | Nearest slide anchor | Visible subject | Likely program | Likely model / scene | Likely date window | Confidence | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `1` | `image6.jpg` | yes | `Sep 1975` | two builders working on a clear / unfinished fighter miniature | fighters | likely early `X-Wing` build work | late `1975` to early `1976` | High | Strong workshop-process image; useful for the early X-wing development phase |
| `2` | `image1.jpg` | yes | `Sep 1975` | rear engine cluster of a large saucer-type ship on a bench | hero ships | likely `Millennium Falcon` rear / engine area | `1976` | Medium-High | Good ship-build evidence, but I would keep the ID slightly cautious until cross-matched |
| `3` | `image5.jpg` | yes | `Sep 1975` | builder detailing the rear engine area of the same large saucer-type ship | hero ships | likely `Millennium Falcon` rear / engine area | `1976` | Medium-High | Very likely the same object family as `image1.jpg` |
| `4` | `image19.png` | yes | `Sep 1975` | builder working on an `X-Wing` in the Van Nuys shop; later red arrow overlay present | fighters | `X-Wing` under construction | late `1975` to early `1976` | High | One of the clearest pure shop-floor X-wing build shots in the PPTX set |
| `12` | `image31.jpg` | yes | `Sep 1975` | builder painting / detailing a large dark surface section on a circular base | Death Star | `Death Star` surface / tile / special section work | `1976` | Medium-High | Strong Death Star build evidence, but exact sub-type still open |
| `16` | `image42.jpg` | yes | `Apr 1976` | wooden internal framework for a large saucer-type ship; small wedge ship also on table | hero ships | probable early `Falcon` structural build with another miniature nearby | `1975-1976` | Low-Medium | Very useful image, but I would keep the identification conservative until cross-matched to a known published caption |
| `23` | `image30.jpg` | no | `Apr 1976` | not yet visually reviewed in this pass | open | open | open | n/a | keep for second-pass review |
| `27` | `image18.jpg` | yes | `Jul 1976` | `Landspeeder` miniature in white / primer with pilot and exposed engine pod assembly | ships and vehicles | `Landspeeder` | `1976` | High | Strong miniature identity |
| `28` | `image26.jpg` | yes | `Jul 1976` | `Landspeeder` miniature in white / primer with pilot; engine pod off to the side | ships and vehicles | `Landspeeder` | `1976` | High | Reads as the same build phase / family as `image18.jpg` and `image24.jpg` |
| `29` | `image24.jpg` | yes | `Jul 1976` | `Landspeeder` in paint-progress on a workbench | ships and vehicles | `Landspeeder` | `1976` | High | Complements the primer-state Landspeeder shots nicely |
| `31` | `image23.jpg` | yes | `Jul 1976` | tracked boxy vehicle maquette with design drawings pinned behind | ships and vehicles | likely `Sandcrawler` maquette / build stage | `1976` | Medium-High | Good process image that links miniature work to design sketches |
| `34` | `image13.jpg` | yes | `Jul 1976` | blurry video frame identifying `Dave Jones` by on-screen text | people / eyewitness | `Dave Jones` identification frame | later documentary use of period footage | High | Better as provenance / people evidence than as model evidence |
| `35` | `image14.jpg` | yes | `Jul 1976` | blurry candid video frame of shop personnel | people / eyewitness | unidentified people in workshop footage | later documentary use of period footage | Low | Probably useful only if matched against surrounding video context |
| `37` | `image17.jpg` | yes | `Jul 1976` | large ANH capital-ship miniature on a workbench | hero ships | likely `Rebel capital ship` program; exact ID not yet locked | `1976` | Medium | Strong shop image, but I do not want to force a more exact ID yet |
| `43` | `image40.jpg` | yes | `Late 1976 / early 1977` | group shop photo with multiple `X-Wings`, `Y-Wings`, and a `TIE` visible | fighters | mixed fighter-program group shot | late `1976` to early `1977` | High | Excellent summary image for the mature battle-program phase |
| `44` | `image41.jpg` | yes | `Late 1976 / early 1977` | row of `X-Wings` with a builder present and a `TIE` nearby | fighters | `X-Wing` lineup / squadron build display | late `1976` to early `1977` | High | Very strong image for the “fleet in service” phase |
| `47` | `image15.jpg` | yes | `Late 1976 / early 1977` | rear-quarter view of a large ANH capital-ship miniature on a workbench | hero ships | likely same large ship family as `image17.jpg`; exact ID still open | `1976` | Medium | Keep paired with `image17.jpg` until the ship identity is closed |
| `11` | `image32.jpg` | yes | `Sep 1975` | file is malformed; cannot be decoded | n/a | n/a | n/a | High | Omit from HTML image rail unless replaced from a clean source |

## What Already Looks Useful

- `X-Wing` build evidence:
  - `image6.jpg`
  - `image19.png`
  - `image41.jpg`
- `Landspeeder` evidence cluster:
  - `image18.jpg`
  - `image24.jpg`
  - `image26.jpg`
- `shop-context / program-density` evidence:
  - `image40.jpg`
  - `image41.jpg`
- `Death Star / large-ship` candidates worth deeper matching:
  - `image31.jpg`
  - `image17.jpg`
  - `image15.jpg`
  - `image42.jpg`

## Strong Next Steps

1. Review the remaining uninspected PPTX images and turn this into a full manifest.
2. Add `research IDs` like `TL-012`, `MTL-006`, or `NF-LS-01` to each reviewed image.
3. De-duplicate near-identical shots and mark whether an image is:
   - `workshop photo`
   - `documentary frame`
   - `book reproduction`
   - `later archival reproduction`
4. If the missing repo becomes visible, connect this manifest to its data model or build pipeline instead of keeping it HTML-only.
