# boheling.github.io

A personal site. Static HTML, no build step, no dependencies — GitHub Pages
serves `index.html` as it is.

- `index.html` — the whole front page, both languages in the markup, one shown
  at a time. Language comes from `?lang=`, then from what was chosen last, then
  from the browser.
- `helix-field-lab/` — an interactive 3D walk through an automated molecular lab
  built into a class C RV. Self-contained.

Preview locally:

```sh
python3 -m http.server 4188
# http://127.0.0.1:4188
```

The films are not here: they live in
[storyshot-gallery](https://github.com/boheling/storyshot-gallery), and the MP4s
themselves are release assets of that repository rather than files in it.
