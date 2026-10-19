# Class XII Biology lessons

Authored lesson drafts for Class XII Biology (chapters 13 to 25), derived from the owner's textbook PDF (`12 Class Data/12th Class Biology.pdf`, source `C12-BIO`). Everything here is a **draft**: nothing is academically reviewed or published, and the import tool never publishes anything. Class XI and Class XII material is never mixed; the Class XI books live in `content/lessons/xi/`.

The files follow the Class XI layout (see `content/lessons/xi/biology/README.md`): `c12-bio-chN-T.json` is the English lesson for topic T, `c12-bio-chN-T-ru.json` the Roman Urdu explanation (`variant_of` the English item), `c12-bio-chN-T.coverage.json` the coverage register (PDF span, every textbook figure and what the lesson carries for it, archived originals, findings), and `figures/` the rendered original figures with `figures.json`.

## Importing into a development API

```bash
python content/tools/import_lessons.py --api http://127.0.0.1:8100 --subject biology --grade 12 --chapter 13
```

The development staff fixtures (`portal-dev-seed-staff`) cover Class XI and XII. Figures are rendered with `node content/tools/figures/render.mjs svg biology 12`.
