// EFC3D: Help content (in-app documentation), English (US).
// MAINTENANCE RULE: every new version updates this file together with the code:
//   1. `versao` and `atualizado` below must match VERSION in server.py (the app warns when they don't);
//   2. a new entry at the top of `novidades`;
//   3. the topics that changed (screens, buttons, shortcuts, generated files).
// Special tags in the topics' HTML (help.js turns them into interactions):
//   <button data-show="#selector" data-tip="text">  highlights the element on screen
//   <a data-go="id">                                 opens another topic
//   <ul class="hl-check" data-id="name">             list of steps with checkboxes (saved)
//   <kbd>                                            key

export const DOCS = {
  versao: '1.58',
  atualizado: '08/11/2026',
  grupos: ['Getting started', 'Step by step', 'Workflows', 'Reference'],
  topicos: [
    // ------------------------------------------------------------------ Getting started
    {
      id: 'visao', grupo: 'Getting started', titulo: 'What is EFC3D', icone: '🦊',
      html: `
<p><b>EFC3D</b> stands for <b>Easy Flexy and Cuts 3D</b>: flexis and cuts in 3D, the easy way.</p>
<p>An app for <b>Mac and Windows</b> that turns a 3D model into a <b>flexi model</b>: articulated, printed in one go, no supports and no assembly. It also splits painted areas into parts that fit together, so you can print each color separately.</p>
<p>Everything runs on your computer: no internet, no account and no subscription.</p>
<h3>The flow, tab by tab</h3>
<ol class="steps">
  <li><b>Model:</b> open an STL, GLB, OBJ or .zip. <button data-show="#s-model" data-tip="Model tab: open or drag the model here">Show on screen</button></li>
  <li><b>Joints:</b> place them where the model should bend. Each joint is checked in seconds with a status light. <button data-show="#s-joints" data-tip="Joints tab: joints">Show on screen</button></li>
  <li><b>Colors:</b> paint the filaments with brush, bucket, height band or line. <button data-show="#s-paint" data-tip="Colors tab: painting">Show on screen</button></li>
  <li><b>Split by color:</b> turn painted areas into snap-in parts (eyes, hair, hands). <button data-show="#s-split" data-tip="Cuts tab: split parts by color">Show on screen</button></li>
  <li><b>Free cut</b> <i>(optional)</i>: draw the line or mark the part with brush or bucket and cut, with a pin or glue only. <button data-show="#s-free" data-tip="Cuts tab: free cut">Show on screen</button></li>
  <li><b>Export:</b> a single button generates 3MF, STLs and plates ready for your printer. <button data-show="#s-exp" data-tip="Export tab: check and export">Show on screen</button></li>
</ol>
<p>The steps are the tabs at the top of the screen (see <a data-go="tela">How the screen is organized</a>). Joints, parts by color and free cuts are <b>complementary</b>: use one, two or all three.</p>
<p>Joints, painted areas, parts by color and free cuts all work the same way: see <a data-go="listas">Lists: select, hide and delete</a>.</p>
<p class="tipbox">💡 First time? Take the <a data-go="tour">guided tour</a> (1 minute) or follow a step by step <a data-go="fluxo-animal">workflow</a>.</p>`,
    },
    {
      id: 'tour', grupo: 'Getting started', titulo: 'Guided tour', icone: '🧭',
      html: `
<p>The tour highlights each part of the screen and explains what it does. Use <kbd>→</kbd> or the Next button to move on and <kbd>Esc</kbd> to exit.</p>
<p><button class="btn primary" data-tour="1">▶ Start the tour</button></p>
<p>The tour does not change anything in your model or project.</p>`,
    },
    {
      id: 'tela', grupo: 'Getting started', titulo: 'How the screen is organized', icone: '🗺',
      html: `
<p>The screen follows the <b>Fusion 360</b> approach: the steps are tabs at the top, each tab has its own toolbar ribbon, the model fills the center and the command options sit on the right.</p>
<h3>At the top</h3>
<ul>
  <li><b>File ▾:</b> Open, Recent, Save project, Save as and the save folder. Next to it, 💾 saves and ↶ undoes. <button data-show="#file-btn" data-tip="File menu">Show</button></li>
  <li><b>Step tabs:</b> 1 Model, 2 Joints, 3 Colors, 4 Cuts (split by color, free cut and plane cut) and 5 Export. <button data-show="#tabs" data-tip="Project steps">Show</button></li>
  <li><b>Toolbar ribbon:</b> the tab's commands, in groups (CREATE, MODIFY, INSPECT...). The lit button is the active mode. <button data-show="#ribbon" data-tip="Step tools">Show</button></li>
  <li>On the right: Help (❓), control by Claude (🤖), light, automatic or dark theme, the <b>marking line thickness</b> (✏ Thin, Medium or Thick selector: applies to every module, lines already drawn change at once and the choice is saved on this Mac; thin is the default) and the <b>language</b> (Português, English, Español). The app opens in your computer's language; your choice is saved. <button data-show="#hdr-tools" data-tip="Help, theme and language">Show</button></li>
</ul>
<h3>Browser (left)</h3>
<p>The project tree: Model, Joints, Painted areas, Parts by color, Free cuts, Plane cuts and Parts. Click a group to expand or collapse it and go to its tab; click an item to select it; 👁 shows or hides. ⟨ collapses the browser. <button data-show="#browser" data-tip="Project browser">Show</button></p>
<h3>Canvas (center)</h3>
<ul>
  <li><b>View</b> (top left): Model, Preview and Exported; in Exported you get Assembled / On the plate, Painting / By part and ↺ Reset positions. See <a data-go="previa">Parts preview</a>. <button data-show="#viewbar" data-tip="Model, Preview and Exported">Show</button></li>
  <li><b>View cube</b> (top right): click a face (Front, Top, Right...) or a corner to look from there; ⌂ returns to the home view. <button data-show="#viewcube" data-tip="View cube">Show</button></li>
  <li><b>Navigation bar</b> (bottom): ⟲ Orbit and ✋ Pan (what the left button does when dragging), ⤢ Fit (frames everything), ⌂ Home, the 3D, Top, Side and Joint views, <b>Display ▾</b> (joint cuts, section, overhang and grid) and <b>Mouse ▾</b>. <button data-show="#navbar" data-tip="Navigation bar">Show</button></li>
</ul>
<h3>Mouse and keyboard</h3>
<ul>
  <li><b>Fusion 360</b> (default): dragging with the middle button pans the view; <kbd>Shift</kbd> + middle button orbits; the wheel zooms toward the cursor; double-clicking the middle button frames everything.</li>
  <li><b>Classic</b>: dragging with the middle wheel zooms. Choose it in <b>Mouse ▾</b>.</li>
  <li>In both: dragging with the left button on empty space orbits and the right button pans. When painting and marking, the left button paints and the right button orbits.</li>
  <li><kbd>F6</kbd> frames everything; <kbd>Home</kbd> returns to the home view.</li>
</ul>
<h3>Command panel (right) and timeline (bottom)</h3>
<p>The panel shows the tab's options: the list, the editor for the selected item and the reports. Clicking the model on a joint, or starting to paint or mark a cut, brings the right tab to the front. ⟩ collapses the panel. <button data-show="#side" data-tip="Command panel">Show</button></p>
<p>The <b>timeline</b> shows the 5 steps with what each one already has (✓ model open, number of joints, areas, cuts, exported parts). Click a step to go to it. <button data-show="#timeline" data-tip="Timeline">Show</button></p>
<p>The status line, right above it, tells you what the app is doing and the suggested next step. <button data-show="#status" data-tip="Status and next step">Show</button></p>`,
    },

    // ------------------------------------------------------------------ Step by step
    {
      id: 'listas', grupo: 'Getting started', titulo: 'Lists: select, hide and delete', icone: '☰',
      html: `
<p>The app's four lists all work the same: <b>joints</b> (Joints tab), <b>painted areas</b> (Colors tab), <b>parts by color</b> (Cuts tab) and <b>free cuts</b> (Cuts tab).</p>
<table class="t">
  <tr><th>On the row</th><th>What it does</th></tr>
  <tr><td>Click the name</td><td>Selects it and shows it on the model.</td></tr>
  <tr><td>👁 / 🙈</td><td>Hides or shows it in the view. Does not change what is exported.</td></tr>
  <tr><td>✕</td><td>Deletes. In parts by color, ✕ leaves the area on the body (not split) and ↺ splits it again.</td></tr>
  <tr><td><kbd>Delete</kbd> or <kbd>Backspace</kbd></td><td>Deletes the selected item in the last list you clicked.</td></tr>
  <tr><td><kbd>⌘Z</kbd></td><td>Brings back what was deleted (the last 40 deletions), with no confirmation dialog.</td></tr>
</table>
<p>The status light on the left (🟢 🟡 🔴 ⚪) always comes with the reason when you click it.</p>
<h3>Marking modes</h3>
<p>Painting (Colors tab), Split by color (Cuts tab) and Free cut marking (Cuts tab) follow the same rules:</p>
<ul>
  <li>The tools use the same letter: <kbd>B</kbd> brush, <kbd>F</kbd> bucket, <kbd>L</kbd> line, <kbd>E</kbd> eraser. Shift + brush or bucket also erases or unmarks.</li>
  <li><kbd>Enter</kbd> closes the line in progress; with no line, it finishes. The button is always <b>✓ Done (Enter)</b>.</li>
  <li><kbd>⌘Z</kbd> undoes the last action inside the mode; right button or Space + drag orbits the view.</li>
</ul>`,
    },
    {
      id: 'previa', grupo: 'Getting started', titulo: 'Parts preview', icone: '🧩',
      html: `
<p>A single preview for everything that becomes a part: <b>parts by color</b> (Cuts tab) and <b>free cuts</b> (Cuts tab) appear together, exactly as they come out in the export.</p>
<ul>
  <li>Open it with the <b>Parts preview</b> button in the Cuts tab, or in the top bar under <b>View › Preview</b>. <button data-show="#t-prevp" data-tip="View › Preview">Show</button></li>
  <li><b>Spread</b>, next to it, pulls the parts apart so you can see the fits. <button data-show="#t-prevp" data-tip="The Spread control appears next to it during the preview">Show</button></li>
  <li>The status light of each area (Cuts tab) and each cut (Cuts tab) comes from this preview, with the reason when you click.</li>
  <li><b>View › Model</b> returns to the model; the preview is kept and <b>View › Preview</b> shows it again without recalculating.</li>
  <li>Changed the painting, an option or a cut? The preview leaves the screen and is rebuilt on the next click.</li>
  <li><b>View › Exported</b> shows the parts from the last export (Export tab), with Assembled / On the plate. Drag a part to move it away and see it better (Shift + drag moves up and down); <b>↺ Reset positions</b> puts everything back. It only changes the view, not the files.</li>
</ul>
<p>While the preview is on screen the joints are locked, so nothing changes by accident.</p>`,
    },
    {
      id: 'arquivo', grupo: 'Step by step', titulo: 'Open, save and recent', icone: '📂',
      html: `
<h3>Open… <kbd>⌘O</kbd></h3>
<p>One button for both a <b>model</b> (STL, GLB, glTF, OBJ or .zip) and a <b>project</b> (.flexiproj). The app decides by the extension. You can also drag the file onto the Model tab area. <button data-show="#btn-open" data-tip="Opens a model or project">Show</button></p>
<h3>🕘 Recent</h3>
<p>The last 10 projects and models opened or saved, with date and folder. Deleted or moved files drop off the list. <b>Clear list</b> empties it. <button data-show="#btn-recent" data-tip="Recent projects and models">Show</button></p>
<p>Models dragged into the window are not added to the list, because the browser does not report where the file is. Use Open… to have them added.</p>
<h3>Save project <kbd>⌘S</kbd> and Save as <kbd>⇧⌘S</kbd></h3>
<p>The project (.flexiproj) holds everything in a single file: the model, the joints, the painting, the palette, the Split by color options, the clearance and the imported cut pieces. It opens the same on another computer, Mac or Windows.</p>
<ul>
  <li>The first time, or with Save as, the app asks where to save.</li>
  <li>After that, ⌘S writes to the same file again.</li>
  <li>When you open another model, the next ⌘S asks again, so it does not overwrite the previous project.</li>
</ul>
<h3>Copy in the export folder</h3>
<p>Every export also saves the full project in its folder. It works as a snapshot of the project at that moment.</p>
<h3>⚙ Save folder</h3>
<p>Exports, test coupons and new projects go to this folder. Default: <code>~/Documents/EFC3D/saidas</code>. Change, Use default or Open in Finder.</p>`,
    },
    {
      id: 'modelo', grupo: 'Step by step', titulo: '1 · Model', icone: '🧊', secao: 's-model',
      html: `
<h3>Formats</h3>
<ul>
  <li><b>STL</b> without color.</li>
  <li><b>GLB, glTF, textured OBJ or .zip</b> containing them (Meshy, Tripo and the like): the painting comes out ready, with colors grouped into filaments. See <a data-go="fluxo-ia">Textured AI model</a>.</li>
</ul>
<h3>On open</h3>
<ul>
  <li>The model is centered and placed on the build plate.</li>
  <li>A file without units becomes <b>120 mm on its longest side</b> (a standing figure ends up 120 mm tall).</li>
  <li><b>Automatic repair:</b> small defects in AI files (edges shared by more than two faces, duplicate triangles, holes) are fixed only where they are, in as many passes as needed. What was done shows up in the model info.</li>
  <li><b>Quality:</b> the model is kept at the file's resolution. Only redundant triangles that do not change the shape are removed (deviation of at most 0.005 mm, ten times smaller than the smallest detail the printer can make). Before 1.28 a large model was reduced to 250 thousand triangles and lost up to 0.13 mm of detail (faceted eyes and face).</li>
  <li><b>Choosing the quality:</b> a model with more than 500 thousand triangles (common in AI figures) opens with a question: 💎 <b>Keep</b> the quality (deviation up to 0.005 mm; slower cuts), ⚖ <b>Medium</b> (recommended: deviation up to 0.02 mm, below what the printer reproduces; cuts about 3 times faster) or ⚡ <b>Low</b> (deviation up to 0.05 mm, as before 1.28; face and fine relief may come out faceted). Each option shows how many triangles remain. You can change it later in Simplify.</li>
  <li>A model with up to 250 thousand triangles opens exactly as it is in the file.</li>
</ul>
<h3>Adjust size and base</h3>
<ul>
  <li><b>Length:</b> changes the size while keeping proportions.</li>
  <li><b>Symmetry:</b> mirrors one side onto the other (fixes crooked models).</li>
  <li><b>Flatten base:</b> trims a little off the bottom so more area rests on the build plate (default 0.3 mm).</li>
  <li><b>Simplify:</b> maximum deviation when removing redundant triangles. It starts with the value of the quality chosen on open (0 for a light model, which stays as in the file). 0.005 mm changes nothing in the print; 0.02 mm is medium quality; 0.05 mm is low. Higher values make the app faster but remove detail.</li>
</ul>
<p>Cuts give the same result at any size: on a large model the app cuts a copy at the reference size and returns it at the real size, with clearances, wall and socket exact in mm (the pin grows with the model).</p>
<p>Changing the size carries everything along with the model: the painting, the joint positions (their size does not change), the lines and marked areas of free cuts, and the planes. Check the joints and run the preview again afterward.</p>
<h3>Create the animal with AI</h3>
<p>Ready-made prompts for ChatGPT: prompt 1 creates the animal image; prompt 2, in the same conversation, generates front, side and back views for a 3D generator. The base texts can be edited and restored.</p>
<button data-show="#s-model" data-tip="Model section">Show the section</button>`,
    },
    {
      id: 'juntas', grupo: 'Step by step', titulo: '2 · Joints', icone: '🔗', secao: 's-joints',
      html: `
<h3>Create joints</h3>
<ul>
  <li><b>＋ Add joint</b> and click the model where it should bend. <button data-show="#btn-add" data-tip="Add joint">Show</button></li>
  <li><b>Suggest joints:</b> the app proposes positions on the thin parts (neck, legs, tail). <button data-show="#btn-suggest" data-tip="Automatic suggestion">Show</button></li>
  <li>Choose the <b>cut piece</b> (the link design) first. See <a data-go="pecas-corte">Cut pieces</a>. <button data-show="#cut-type" data-tip="Cut piece for the next joints">Show</button></li>
</ul>
<h3>Edit with the mouse (like in Bambu Studio)</h3>
<ul>
  <li><b>All (A):</b> drag the piece to move it (Shift moves up and down), the rings to rotate (Shift in 15° steps) and the handles to scale. Faces change one axis; corners change all of them.</li>
  <li><kbd>M</kbd> move, <kbd>R</kbd> rotate, <kbd>S</kbd> scale leave only one tool.</li>
  <li>Option + wheel changes the scale. Arrow keys nudge 0.5 mm (Shift: 0.1 mm); PageUp and PageDown move up and down.</li>
  <li><b>Axes:</b> the arrows follow the joint or the world.</li>
</ul>
<h3>Joint panel</h3>
<ul>
  <li>Name, cut piece, position, rotation and scale per axis (lock for uniform scale).</li>
  <li><b>Fit size to location:</b> scales the joint to the model's cross section at that point.</li>
  <li><b>Flip side</b>, <b>Mirror</b> (creates the joint on the other side) and <b>Duplicate</b>.</li>
  <li><b>Cut limits:</b> trim only the cut piece's plate; the links are never trimmed. "Limits from section" calculates them automatically.</li>
  <li><b>Cut inside the edge:</b> cuts only the part where the joint is.</li>
  <li><b>Clearance for this joint only.</b></li>
</ul>
<h3>Status light</h3>
<p>Each joint is checked: it separates the parts, real clearance, links, part trapped in 26 directions, thickness of links and hooks, skin, floating parts and overlap with other joints or fits.</p>
<table class="t">
  <tr><td>🟢 green</td><td>OK</td></tr>
  <tr><td>🟡 yellow</td><td>warning: it prints, but read the reason</td></tr>
  <tr><td>🔴 red</td><td>problem: the export asks for confirmation</td></tr>
  <tr><td>⚪ white</td><td>not checked yet</td></tr>
</table>
<p>In the list: 👁 hides the joint in the view, ✕ or <kbd>Delete</kbd> deletes it and <kbd>⌘Z</kbd> brings it back. See <a data-go="listas">Lists</a>.</p>`,
    },
    {
      id: 'pecas-corte', grupo: 'Step by step', titulo: 'Cut pieces', icone: '⛓', secao: 's-joints',
      html: `
<p>The cut piece is the joint design: the links and the plate that separates the parts.</p>
<table class="t">
  <tr><th>Piece</th><th>Author</th><th>Recommended use</th></tr>
  <tr><td>Arch (RLA)</td><td>own</td><td>General use (body, neck). Two D links with 45° faces. The default piece.</td></tr>
  <tr><td>Low Arch (RLA)</td><td>own</td><td>Thin seam and little depth; the best fit for thin parts.</td></tr>
  <tr><td>Large Arch (RLA)</td><td>own</td><td>Large parts.</td></tr>
  <tr><td>Shell (RLA)</td><td>own</td><td>Curved seam that hides the joint.</td></tr>
  <tr><td>Compact Shell (RLA)</td><td>own</td><td>Curved seam on smaller parts.</td></tr>
  <tr><td>Diamond Link (RLA)</td><td>own</td><td>Body and neck. Green from about 11 mm. Almost no overhang.</td></tr>
  <tr><td>Double Link (RLA)</td><td>own</td><td>Wide, flat parts. Stronger and does not twist.</td></tr>
  <tr><td>Diamond Swivel (RLA)</td><td>own</td><td>Legs and arms. Swivels sideways and a little up and down.</td></tr>
  <tr><td>T Anchor (RLA)</td><td>own</td><td>Tail, ear and low parts: green at about 7 mm tall.</td></tr>
</table>
<p>RLA joints have faces at 45° or more (they print without supports) and were tested in a block: they separate, stay trapped in all 26 directions and bend 3° to 9° per joint.</p>
<h3>Import your own cut piece</h3>
<p>The <b>Import cut piece…</b> button (STL). It goes into the library and travels inside the projects that use it.</p>
<p class="tipbox">⚖ Every cut piece in the app is our own (RLA LABS). An old project that used FJM, Projectcutter or flexicutter (third party, out of the app since 1.50) opens with the own joint in the same place and the scale redone: check each joint. On very thin parts (the legs of a small model) the own joint may not fit strong: scale the model up, use the Low Arch or import a cut piece you have the right to use.</p>`,
    },
    {
      id: 'cores', grupo: 'Step by step', titulo: '3 · Colors', icone: '🎨', secao: 's-paint',
      html: `
<p>Click <b>🖌 Paint the model</b>. Color 1 is the base filament (unpainted); up to 16 filaments. Joints are hidden while you paint. <button data-show="#btn-paint" data-tip="Enter painting mode">Show</button></p>
<h3>Tools</h3>
<ul>
  <li><b>🖌 Brush <kbd>B</kbd>:</b> left button paints, Shift erases (back to color 1). Option + wheel or <kbd>[</kbd> <kbd>]</kbd> change the size. "Paint visible side only" keeps it from bleeding through to the back.</li>
  <li><b>🪣 Bucket <kbd>F</kbd>:</b> paints the area connected to the clicked point; the preview appears on hover.
    <ul><li><b>Direction:</b> stops where the surface turns beyond the angle limit (good on smooth models).</li>
    <li><b>Creases:</b> stops at sharp edges, like in OrcaSlicer.</li>
    <li>180° paints the whole part.</li></ul></li>
  <li><b>🧽 Eraser <kbd>E</kbd>:</b> drag to erase paint (back to color 1). Closed lines it touches are removed too. It uses the brush size; <kbd>⌘Z</kbd> undoes.</li>
  <li><b>▤ Height band <kbd>H</kbd>:</b> paints between two Z heights, with an exact edge. Click picks "From Z"; Shift + click picks "To Z".</li>
  <li><b>✏ Line <kbd>L</kbd> (formerly Outline; <kbd>C</kbd> also works):</b> for AI figures, where the bucket bleeds. Click points around the area: the line follows the surface. Close it on the first point or with <kbd>Enter</kbd>; the mode switches to "Paint inside". Hover to see the area and click. If the area leaks, a warning appears before painting. <kbd>Backspace</kbd> undoes the last point.</li>
</ul>
<button data-show="#tool-seg" data-tip="Painting tools (appear while painting)">Show the tools</button>
<h3>Painting shortcuts</h3>
<p><kbd>1</kbd> to <kbd>9</kbd> pick the color; <kbd>⌘Z</kbd> undoes; right button or Space + drag orbits the view; <kbd>Enter</kbd> or <b>✓ Done</b> exits.</p>
<h3>Painted areas</h3>
<p>Below the palette is the list of painted areas, with color and size in mm². Click to highlight the area on the model; 👁 hides the color in the view; ✕ or <kbd>Delete</kbd> erases that area's paint (back to color 1) and <kbd>⌘Z</kbd> brings it back. <b>Erase specks</b> clears all very small areas at once. <button data-show="#area-box" data-tip="Painted areas">Show</button></p>
<h3>Textured model</h3>
<p>The "Texture colors" box redoes the painting with a different number of filaments (automatic or 2 to 8) and cleans up small specks.</p>
<p>Colors follow the joint cuts and come out in the 3MF, each part pointing to its filament.</p>`,
    },
    {
      id: 'separar', grupo: 'Step by step', titulo: '4 · Cuts: split by color', icone: '✂', secao: 's-split',
      html: `
<p>Each painted area can become a part to print separately and snap in. It does not touch the joints or the open model.</p>
<ul class="hl-check" data-id="separar-uso">
  <li>Paint the parts (Colors tab).</li>
  <li>Click <b>✂ Split by color</b>. Small specks start unchecked.</li>
  <li>Click an area on the model or in the list and choose the type and options.</li>
  <li><b>Parts preview</b>: the parts appear spread apart, together with the free cuts, and each area gets its status light.</li>
  <li><b>✓ Done (Enter)</b> and export in the Export tab.</li>
</ul>
<p>In the list, ✕ leaves the area on the body (it does not become a part) and ↺ splits it again; <kbd>Delete</kbd> does the same for the selected item and <kbd>⌘Z</kbd> undoes.</p>
<p><b>Part name (1.58).</b> Select the area and type in the <b>Name</b> field, as with free cuts. The name shows in the list, in the preview, in the report and in the 3MF. Repeated names get a number, and an empty field goes back to the default name (Color N · area K). Free cuts drawn on that part follow the change.</p>
<button data-show="#btn-split" data-tip="Opens the Split by color module">Show</button>
<h3>Cut types</h3>
<table class="t">
  <tr><th>Type</th><th>When to use</th></tr>
  <tr><td>Automatic (default)</td><td>Plug whenever it fits, also on a relief (eyebrow, button), whose side walls come out whole with the part (on a relief, only if it comes out with no warning); otherwise, by painting.</td></tr>
  <tr><td>By painting</td><td>Any shape: hair, face, hands, feet. The part is the volume closest to the painted area and it also separates parts that touch the body.</td></tr>
  <tr><td>(Inset) plug</td><td>Eye, nose, emblem: a straight prism that goes into the body.</td></tr>
  <tr><td>Limb</td><td>Arm, leg, tail: cuts the whole part with a plane (flat face, no supports) or following the painted edge (curved face).</td></tr>
</table>
<h3>Options</h3>
<ul>
  <li>Plug <b>Depth</b> (default 2 mm) and <b>Clearance</b> (default 0.3 mm, for gluing).</li>
  <li><b>Maximum thickness</b> (by painting): limits the part to a shell.</li>
  <li><b>Smooth edge</b> (automatic): edge without grooves.</li>
  <li><b>Tilt arrow:</b> direction in which the plug goes in. With no tilt, if part of the model is in front of the area (a lock of hair over the eyebrow), the app finds the nearest free direction by itself, up to 40°.</li>
  <li><b>Pin</b>, on any type: on the body (recommended), snap lock (no glue), pin on part or loose dowel. Diamond pins: they print without supports and do not rotate.</li>
</ul>
<h3>Checks</h3>
<p>Smooth edge, clear insertion direction, wall of 1.2 mm or more behind the fit, minimum thickness and width, pin that fits, real measured clearance and, for a limb, a plane close to the painted edge.</p>
<p><b>The whole painting comes out with the plug.</b> The part has exactly the painted shape (the eyebrow with the width and walls of the relief, the eyelashes of the eye); the clearance comes out of the pocket in the body, which is that much larger around it. Nothing of the painting stays on the body as a thin blade. Only the bit under another part of the model (the tip of the eyebrow under a lock of hair) cannot come out straight: it stays on the body, hidden, and the report says how much.</p>
<p class="tipbox">🔧 Press fit without glue: test a clearance of 0.10 to 0.15 mm on your printer.</p>`,
    },
    {
      id: 'corte-livre', grupo: 'Step by step', titulo: '4 · Cuts: free cut', icone: '✏', secao: 's-free',
      html: `
<p>Cut any part by <b>drawing the cut line</b> or <b>marking the part with brush or bucket</b>. No painting needed: marking does not change the print color. The cut only takes what you indicated: it is not an infinite plane like in a slicer, so cutting one leg does not cut the other.</p>
<p>Use it when the automatic cut fails, for example on an AI model where one arm came out fused to the body and the other did not. <button data-show="#s-free" data-tip="Cuts tab: Free cut">Show on screen</button></p>
<h3>How to use</h3>
<ul class="hl-check" data-id="corte-livre">
  <li>Click <b>✂ New cut</b>. <button data-show="#fc-new" data-tip="Creates a cut and opens marking">Show</button></li>
  <li>Choose the tool and indicate the part that will come off (details below). <button data-show="#fc-new" data-tip="The tools appear when you create a cut">Show</button></li>
  <li>Press <kbd>Enter</kbd> or click <b>✓ Done</b>.</li>
  <li>Choose the <b>fit</b> and the <b>cut shape</b>.</li>
  <li><b>Parts preview</b>: the parts appear spread apart, together with the parts by color, and each cut gets its status light.</li>
  <li>Export in the Export tab, on its own or together with joints and parts by color.</li>
</ul>
<h3>The tools</h3>
<table class="t">
  <tr><th>Tool</th><th>How to use</th><th>When to use</th></tr>
  <tr><td>✏ Line <kbd>L</kbd></td><td>Click points around the part; the line follows the surface. The first point or <kbd>Enter</kbd> closes it; <kbd>Backspace</kbd> undoes the last point. <kbd>Enter</kbd> closes along the missing stretch, without going back over what you drew: click only the front of the neck and it closes around the back, even when hidden by the hair.</td><td>Where there is no sharp edge: neck, shoulder and waist of AI figures.</td></tr>
  <tr><td>🖌 Brush <kbd>B</kbd></td><td>Drag over the part that will come off. Shift + drag unmarks. <kbd>[</kbd> and <kbd>]</kbd> change the size.</td><td>Small parts, touch-ups and edge fixes.</td></tr>
  <tr><td>🪣 Bucket <kbd>F</kbd></td><td>Hover to see the area and click. Shift + click unmarks. It stops at lines of the same cut.</td><td>Parts with a sharp edge (boot, helmet) or after a line.</td></tr>
  <tr><td>🧽 Eraser <kbd>E</kbd></td><td>Drag to unmark. Lines it touches are removed too; on the line in progress, only the touched points are removed and you continue with <kbd>L</kbd>. <kbd>[</kbd> and <kbd>]</kbd> change the size.</td><td>Fixing what went past the edge.</td></tr>
</table>
<ul>
  <li><b>The marked area is the part that comes off.</b> Its edge becomes the cut line; if the area has several edges (the head and the two braids), each edge becomes a line.</li>
  <li><b>The combination that solves AI models:</b> draw the <b>line</b> where the part should separate and use the <b>bucket</b> on the side that comes off. The bucket stops at the line, so it does not leak.</li>
  <li>Loose brush specks are ignored and small holes in the marking are filled.</li>
  <li><kbd>⌘Z</kbd> undoes the last action; right button or Space + drag orbits the view.</li>
</ul>
<h3>Fits</h3>
<table class="t">
  <tr><th>Fit</th><th>What for</th></tr>
  <tr><td>Glue only</td><td>No pin. The faces fit with the chosen clearance (default 0.2 mm) and you glue with CA or epoxy.</td></tr>
  <tr><td>Round pin (rotates): the part turns</td><td>Pin on the body and hole in the part, with 0.4 mm clearance: the part turns (head, arm). The cut face stays flat so it can turn.</td></tr>
  <tr><td>Rotating pin with lock</td><td>Turns and does not come out: a ring with a ramp snaps in with a click. Needs at least 2.8 mm of pin.</td></tr>
  <tr><td>Fixed pin (diamond)</td><td>Aligns the part and does not rotate. Good for gluing in the right spot.</td></tr>
  <tr><td>Snap lock</td><td>Split pin with a barb: fits without glue and does not rotate.</td></tr>
  <tr><td>Pin on part</td><td>The pin comes out of the part and the hole is in the body.</td></tr>
  <tr><td>Manual connector</td><td>The cut comes out with the faces only (razor) and you place the connector after the preview. See below.</td></tr>
</table>
<h3>Manual connectors (you place them)</h3>
<p>For when you want to decide the fit instead of letting the app choose. The cuts stay the same: the manual connector is one more option, in a separate module, and it does not change the automatic cut.</p>
<ol>
  <li>On the cut, choose the fit <b>Manual connector: you place it after the preview</b>.</li>
  <li>Click <b>Parts preview</b>. In <b>Manual connectors</b>, just below the list of cuts, each joint of that cut shows up with a suggested connector: at the point of the face farthest from the skin, with the largest diameter that leaves a 1.2 mm wall, the pin on the smaller piece and the hole in the larger one.</li>
  <li>Choose the connector (C1, C2…) and change what you want: <b>Type</b> (pin with a flat side, which does not turn; round pin, which turns; loose dowel; magnet hole on both sides; or no connector), <b>Diameter</b>, <b>Depth</b> in each piece, <b>Axis</b> (perpendicular to the face or vertical to the bed, so the piece prints standing), <b>Flat side rotation</b>, <b>Clearance</b> (0.4 mm by default; 0.2 mm for the magnet, which is glued) and <b>⇄ Swap side</b>.</li>
  <li>To change the spot, click <b>⌖ Move connector</b> and then the joint face (use <b>Spread</b> at the top to see the faces). The connector goes to the point of the face nearest the click.</li>
  <li>Every change is checked right away, with text and a symbol (✓ fine, ⚠ warning, ✕ error): edge of the face, wall around and under the hole, a hole that would break out of the skin, and two connectors that meet inside the same piece (the middle piece, like the neck, has to stay solid).</li>
  <li>Click <b>✓ Apply to pieces</b>. The cuts are not redone: only the pins and holes of the joint's pieces. A connector marked ✕ is left out until it is fixed.</li>
</ol>
<p>You can put more than one connector on the same joint (<b>＋ Another connector on this joint</b>), for example two pins on a wide waist. The connectors go into the saved project and come out in the export.</p>
<h3>Socket: the part goes into the body</h3>
<p>On by default for new cuts (<b>Part goes into the body (socket)</b>). On a line that goes around a part (neck, wrist, tail), the part gets a plug that goes into the body down to the <b>socket depth</b> (default 4 mm), and the body gets the cavity. The plug has straight walls, 1.2 mm inside the line, and a flat bottom. When the line is not too tilted (up to about 50 degrees), the plug is vertical to the build plate: the body prints upright with the socket and pin straight, and the part stands on the bottom of the plug. The clearance between plug and cavity is exactly the one chosen. The body always keeps at least 1.2 mm of wall on the outside, so the cavity never breaks through the collar or the back. Lines that outline a part lying on the body (a braid on the chest) get no socket, and a part that is too thin (less than 4 mm wide) gets only the cut face; the app warns you. The pin, if any, sits at the bottom of the socket. It does not apply to the rotating pin (the walls would lock it).</p>
<p><b>Standard pin.</b> Since 1.43 the fit is a pin with one flat side, at the centre of the section and on the part's axis, like hand-made parts (a crooked line does not tilt the pin). The pin is half the part's width (leaving a 1.2 mm wall plus the pin clearance around it), goes the socket depth into the body and has a chamfered tip; the body gets the hole with the pin clearance. The flat side stops it from turning. On a wide section (more than about 24 mm, like a waist or a torso) the plug the size of the whole section stays. The pin stands upright on the plate when the axis is within 20 degrees of vertical. Since 1.45, with a flat face, the pin comes out perpendicular to it when that direction is closer to vertical than the part's axis (up to 25 degrees): the piece stands upright on the other one, like the neck holding the head, with no support. Part too thin for a pin: only the cut face, with a warning. When another cut passes just below (head and neck cut close together), the pin comes out of the middle part into the piece: the middle part stays solid, with a pin on both sides.</p>
<p><b>Razor socket.</b> The walls and bottom of the plug are computed exactly from the line, not from a grid of points: they come out smooth with crisp edges, without the staircase. Where the outer skin is too close (the shoulder inside the sleeve, for example), the plug steps back only there so the body keeps its wall.</p>
<p><b>Cut like a blade.</b> Around a part, the cut face is the smooth surface that passes exactly through the drawn line. On a part lying on the body, the separation follows the body underneath it: the part comes off whole and the body stays smooth where it was. Designed for printing: smooth faces rest well on the build plate and need fewer supports, and each part can come out in its own color without an AMS. Thin edges next to the cut (less than 0.8 mm, which the nozzle cannot print) go to the neighboring part; the report says how much.</p>
<h3>Flat ring at the joint (optional)</h3>
<p>With the socket on, <b>▭ Flat ring at the joint (rests on the plate)</b> appears. The face around the socket, which follows the line and undulates, becomes a plane facing the plug axis on both parts, and the wall at the socket mouth becomes 2 mm. That way the body can rest on the build plate on this ring and the part sits flat against it. Only the ring between the skin and the socket changes: the socket bottom and the rest of the parts stay the same. On the skin, the boundary becomes straight in that stretch (the report says how many mm it rises or drops relative to the drawn line). It is off by default, so it does not change cuts that already work. If the line rises and drops too much (the outline of the face) or the plane would affect another part, the app does not apply it and warns you.</p>
<p>Tilted or curved line (the hairline, which runs from the forehead down to the nape): the socket bottom follows the cut face, always at the chosen depth below it, and the body does not end up hollow. With an almost flat line (neck, wrist) the bottom stays flat, standing on the build plate.</p>
<p>If the line of another cut runs just below (head and neck cut close to each other), the socket gets shallow enough for the middle part to keep a 1.2 mm bottom; if not even a shallow socket fits, that joint stays with just the cut face, to glue. So a short neck never comes out as a hollow cup. The report warns.</p>
<p>Several lines in the same cut around separate areas (two eyes, two eyebrows): each area is cut on its own and comes out as one part. For shallow relief (eyebrow), draw the line on the skin around the base of the relief: whatever is inside the line is the part.</p>
<p>The fit, the pin and the socket also appear during marking, right below the tools: you can choose before finishing.</p>
<h3>Came out without a pin?</h3>
<p>The pin needs material around it: the lock needs a cross section of about 5 mm or more; the fixed pin (diamond) fits in slightly smaller sections. On a thin part (the wrist of a small figure, for example) the cut comes out without a pin, the status light turns yellow and the list shows <b>⚠ no pin</b>. To get a fit anyway: turn on the <b>socket</b>, reduce the <b>pin clearance</b>, switch to a <b>fixed pin</b>, or cut at a thicker spot.</p>
<p>When the part touches the body at more than one spot, the pin goes at the contact next to the line you drew.</p>
<h3>Cut shape</h3>
<ul>
  <li><b>Automatic</b> (default): if the line stays close to a plane (up to 10% of the part's width and at most 1 mm), the cut face is that plane, like a hand-made part: straight seam, firm fit and a flat face for the build plate. If the line goes up and down more than that, or if the plane would take skin from outside the line (a sleeve hem) or split the body, the face follows the line. The report says which one was used. Works for any model: neck, tail, paw, tentacle, mug handle. Since 1.45: when the part is stuck to another one next to the line (the neck at the chin, the arm at the armpit) and the pure plane does not separate it, the face is flat in the middle, where the pin goes, and only within 1.5 mm of the line follows the skin. This also applies to a cut on an already cut piece.</li>
  <li><b>Follow the line</b>: the cut face is a smooth surface that passes through the line you drew. Good for irregular cuts, like a collar or a pant hem.</li>
  <li><b>Plane through the line</b>: the best plane through the line, but only inside it. The face is flat and the part rests on the build plate without supports.</li>
  <li><b>Plug: straight walls (beta)</b>: the area inside the line comes out like the plug of the color cut. The walls are straight along the fitting direction (the app finds a free direction, tilting up to 40° if needed), the bottom is flat 2 mm below the lowest point of the area and the clearance is the same all around (0.3 mm by default; change it in <b>Clearance between faces</b>). With a line, the seam lies exactly on it; with an area marked by brush or bucket, the edge is smoothed as in the color cut. The piece fits firmly in a pocket with crisp edges and lies flat on the bed. It works for what is seen whole from one side: shell, eye, lid, emblem, face from the front. On an arm, a leg or a part that wraps around, it refuses and says why; then use another shape. Fits: glue only, fixed pin, lock, pin on the piece or dowel (it does not turn and does not use the manual connector).</li>
</ul>
<p><b>Hidden joint under a layer.</b> When the line sits in the crease where the part goes into a layer on top (the arm into the sleeve, the leg into the trouser hem, the paw into the fur) and the plane would take a bit of that layer, the part continues under it as a plug with the part's own section and a flat bottom, and the layer stays whole on the body. The seam is hidden in the crease, like hand-made parts. If that does not work either, the cut follows the line as before.</p>
<h3>Is the part attached somewhere else?</h3>
<p>With a <b>marked area</b>, the part may touch the body along a strip (braids on the shoulder and chest, hand on the leg): if the edge alone does not separate it, the app cuts along the <b>smallest surface through the marked edge</b>, like a soap film held by the edge. The part stops at the edge (it does not take a piece of clothing or dig into the body) and the contact faces follow the marking. The cut comes out smooth, as if made by a blade, and follows the line: an outlined braid comes off whole and the kimono around it stays on the body, even if the line passed with some slack. Example: mark the whole head with the braids; they come off together with the head and the pin goes only in the neck (the largest contact). At the other contacts the part is just seated, for gluing. Along a line that goes around a part (neck, wrist), the cut face follows the smooth blade through the line: the edge on the skin lies on the drawn line, like a razor cut, and the socket ring comes out smooth. The razor edge is kept only if the skin on both sides stays whole on the right side: where the blade would cross the skin away from the line (a lock of hair resting on it, a fold of clothing) and open a slit, that cut stays with the grid.</p>
<p><b>Razor or skin: the app chooses per cut (1.57).</b> Each free cut is first tried as a <b>razor</b> cut: a smooth blade through the line, which leaves a flat face and a clean edge. It is kept when the seam stays on the drawn line (within 1 mm overall and 2 mm at the worst point), on the piece and on what is left of the body. Where another layer covers the part (the sleeve hem around the arm), the blade is trimmed to the shadow of the piece so it does not open a slit in that layer. If the blade would leave the line (a line that goes up and down around a belt, for example) or the part does not come out with a blade (hair, face, ear), the cut is made <b>along the skin</b>, which puts the seam exactly on the line. The result of each cut says which of the two made it. In both cases the socket is added at the end, after all the cuts, and never goes through a thin piece. For the razor to be used, draw the line as straight as possible around the part. The option "Use the previous engine (1.44) on this cut" still works.</p>
<p><b>Cut along the skin (1.48 beta).</b> The free cut now splits the model's skin exactly on the line, without recomputing the outer surface: the shape of the model does not change (no slit in the sleeve, no flap, no leftover). Each side is closed on the inside with a new face, the same one for both pieces, with the clearance in between. That face is built along the piece's <b>fitting direction</b>, so it goes in and out straight: the app suggests the direction (shown in the cut result, with azimuth and elevation) and you can choose another one in <b>Fitting direction</b> in the cut options (for example, hair that comes down from above). The pin goes in the same direction, through the connectors module. A cut this engine cannot make (area marked with brush or bucket, a piece that turns) is made by the previous engine, with a warning; you can also ask for the previous engine on a cut.</p>
<p><b>Exact skin at the edge (1.47).</b> When the cut stays with the grid, the grid used to cut diagonally across the corner where one part meets the other (a lock of hair and the forehead), and the edge on the skin ended up 0.5 to 1.5 mm inside the line: a smooth strip of forehead came out stuck to the lock. Turn on <b>✂ Exact edge on the skin (slower)</b> on the cut: within 1.5 mm of the line, the skin that belongs to the piece goes back to it, and the boundary runs halfway between the skin of the piece and the skin of the body, so it reaches the crease, as a hand cut would. The line is handled in stretches: a stretch that would open a hole or break off a bit (a thin lock resting on the skin) stays as it was. The cut takes longer (up to about 2 minutes more).</p>
<p>With a <b>line</b>, the side of each line says which is the part. If the part also touches the body at a spot the line did not catch (hair resting on the collar, behind the neck), the app completes the cut there along the smallest edge and shows where, in yellow. If you prefer another spot, click <b>✏ Edit marking</b> and draw a line there.</p>
<h3>Other options</h3>
<ul>
  <li><b>Invert:</b> with a marked area, the part is the area; without an area, it is the smaller side of the line. Check it to keep the other side.</li>
  <li><b>Pin clearance</b> (default 0.4 mm) and <b>pin width</b> (automatic from the cross section size).</li>
  <li>In the list: 👁 hides the cut in the view, ✕ or <kbd>Delete</kbd> deletes it and <kbd>⌘Z</kbd> brings it back.</li>
  <li><b>Cutting in sequence (hide the part):</b> after the preview, a cut's 👁 also hides its part, and clicks go through it. You can then draw or paint what was underneath: with the hair and the face hidden, the line around the neck reaches the nape. Cuts are made in list order, so the new cut works on the part left by the previous ones. Only the view changes: the line is still stored on the original surface, and the preview and the export keep every part. The 👁 of the parts by color (Colors tab) does the same. At the top of the list is the <b>Body</b> row, what is left after the cuts: when the line goes around the face, the Body is the hair, and that is what you hide to reach the neck.</li>
  <li><b>A part between two lines (the neck):</b> a part between two others needs two edges. Make one cut just below the chin (separates the head) and another at the collar (separates the neck from the torso). When a cut is on a part that came out of an earlier cut and would separate nothing over the whole model, the app redoes it looking only at that part (the hair already separated no longer links the head to the neck) and says so in the report.</li>
  <li><b>✂ New cut on an already cut part:</b> the right way to cut what only shows up after another cut. Example: in the original model the hair and the nape are a single mesh, and the nape only exists after the hair cut, as a cut face. Click <b>✂ New cut on an already cut part</b> and then the part (the app runs the preview if needed). The part appears alone, solid, as it came out of the cut, and the marking is the same as in Free cut, with every tool: <b>✏ Line</b>, <b>🖌 Brush</b>, <b>🪣 Bucket</b> and <b>🧽 Eraser</b>, the L, B, F and E keys, ⌘Z, the joint, the pin and the socket. All of it also works on the cut faces. The sides of the marking are found on the part itself, so painting the head with the bucket, or running the neck line through the nape, frees the head. Enter finishes and goes back to the whole model. In the list the cut shows as "on part …"; <b>Edit the marking</b> goes back to the part with the marking as it was. If an earlier cut is edited and the part changes, the app warns and the marked area is redone. Cuts marked on the whole model work as before.</li>
  <li>Cuts are saved in the project (.flexiproj).</li>
</ul>
<h3>Cut inside a part that was already cut</h3>
<p>Yes: a cut can take a part that came out of another cut (cutting the top of a head that already came off the body, for example). The cut acts on the part where the line is, and the app applies the cut of the larger part (the head) first and then the cut inside it (the top), in whatever order you created them.</p>
<p><b>Flexi that is already articulated.</b> On a print in place model (legs and joints already interlocked, apart only by the clearance), the parts that fit into each other stay one piece after the cut: they come out assembled, in the model's position, and print as they are. The cut piece takes only what is on the marked side of the line.</p>
<p><b>Cuts that depend on another cut.</b> A cut made on the piece of another cut depends on it: the source cut always runs first. Deleting the source cut, or changing its marking (lines, area, side), also deletes the cuts drawn on its piece, and their own dependents. The app warns first with the list ("Deleting Cut 12 also deletes the cuts drawn on its piece: Cut 13, Cut 14") and <kbd>⌘Z</kbd> brings them all back. Renaming the source cut carries the new name to the dependent cuts. If the source cut does not come out, the dependent cuts do not run and the report says why.</p>
<h3>Combining cut types (color, free and plane)</h3>
<p>The order is always the same: first <b>Split by color</b>, then the <b>Free cuts</b> and finally the <b>Plane cuts</b>. Each cut acts on the part it is in, and the app checks each result:</p>
<p><b>The list order does not change the pieces.</b> Since 1.44 the app picks the order of the free cuts by itself, from the lines: first the cuts on the model, from the larger part to the smaller (like cutting by hand: the large part comes out whole and then its details), then the cuts on a piece, also from the larger to the smaller (the parent piece before the piece cut inside it). With two cuts one inside the other (the head and the neck right below it), each piece keeps the name of the cut whose line marks it on the whole model. Deleting and recreating a cut (it goes to the end of the list) or creating the cuts in another order gives the same pieces.</p>
<ul>
  <li><b>Line over a separation that already exists</b> (the hair edge already split by color): the free cut is not redone, so it does not shave a sliver off the seam, and it gets a yellow warning naming the two parts. To get the free cut's socket or pin at that joint, uncheck <b>Split</b> for the area in the Colors tab (or delete the free cut).</li>
  <li><b>Parts never share material</b>: if a cut would leave a piece of the rest inside the part (a loose sliver inside the hair, for example), it is removed from the rest and the status light warns you.</li>
  <li><b>Slivers</b>: a cut that would only remove a sliver of less than 1 mm³ does not become a part (red status light); tips of up to 2 mm³ that a cut or plane breaks loose are discarded, because loose they do not print.</li>
  <li><b>Cut that would take the whole part</b> (nothing on the other side of the line): it turns red and does not generate an empty part. Check the side with <b>Invert</b>.</li>
</ul>
<p class="tipbox">💡 Difference from <a data-go="separar">Split by color</a>: there the part is the painted area, with an inset fit (plug) or limb. Here you just draw where to cut.</p>`,
    },
    {
      id: 'corte-plano', grupo: 'Step by step', titulo: '4 · Cuts: plane cut', icone: '▭', secao: 's-plane',
      html: `
<p>The slicer cut (OrcaSlicer, Bambu Studio): a <b>plane</b> with height and tilt in any direction goes through <b>everything it crosses</b> and splits each part in two, with flat faces. It has its own section, separate from Free cut, and runs after it. <button data-show="#s-plane" data-tip="Section 6: Plane cut">Show on screen</button></p>
<h3>How to use</h3>
<ol>
  <li>Click <b>▭ New plane</b>. The plane appears in the middle of the model, lying flat.</li>
  <li><b>↕ Height</b>: drag the arrow to raise or lower the plane, or type the center height. <b>Move along normal</b> moves the plane in the direction it points.</li>
  <li><b>⟳ Rotate</b>: drag the rings to tilt in any direction, or type the tilt in X and Y. Shortcuts: <b>Flat</b>, <b>Upright (front)</b>, <b>Upright (side)</b>. <b>⇅ Flip</b> swaps which side is the top (the ▲ arrow).</li>
  <li>The <b>blue line</b> on the model shows where the plane cuts.</li>
  <li>Choose the <b>connector</b> and click <b>Parts preview</b>.</li>
</ol>
<h3>Connectors</h3>
<ul>
  <li><b>None</b>: flat faces touching, for gluing.</li>
  <li><b>Fixed pin (diamond)</b> on the bottom or top part: aligns and glues.</li>
  <li><b>Snap lock</b>: fits without glue.</li>
  <li><b>Loose dowel</b>: a separate pin and a hole on both sides, like the slicer's dowel.</li>
</ul>
<p>One connector goes in the middle of each cut part, at the point farthest from the edges. The default pin clearance is 0.4 mm. A section that is too small gets no connector, and the report warns you.</p>
<h3>For printing</h3>
<p>Each cut face goes on the build plate: both parts print resting on the flat face, with fewer supports. Also use it to split colors without an AMS (cut the head in another color, for example).</p>
<p>If the plane passes through more than one part on the same side (both legs), each one becomes a part. <b>Cut: body only</b> does not touch parts that already came out of other cuts.</p>
<p><b>Cut: only the part where the plane's center is.</b> Move the plane's center inside the part you want to cut and only that part is cut, even if it already came out of a cut; the others stay whole. This is how to separate a part held at more than one point. Example, on a figure whose chin touches the collar: after cutting the hair, a plane just below the chin separates the head (it cuts the neck and the chin contact at once) and another plane at the collar separates the neck from the torso. Thin sheets the plane grazes (under 0.6 mm) go to the neighboring part.</p>
<p class="tipbox">💡 Difference from <a data-go="corte-livre">Free cut</a>: there only the part indicated by the line comes off, with a cut face that follows the line. Here the plane cuts straight through everything it crosses.</p>`,
    },
    {
      id: 'exportar', grupo: 'Step by step', titulo: '5 · Export', icone: '📦', secao: 's-exp',
      html: `
<h3>What will be exported</h3>
<p>The box shows whether joints, parts by color or both will be exported. <button data-show="#exp-plan" data-tip="Export plan">Show</button></p>
<h3>Before exporting</h3>
<ul>
  <li><b>Printer:</b> sets the build plate used for the plates. <button data-show="#printer" data-tip="Printer and build plate size">Show</button> See <a data-go="impressoras">Printers and plates</a>.</li>
  <li><b>Joint clearance:</b> default 0.4 mm. Use the <a data-go="calibracao">calibration coupon</a> to find the right one for your printer. <button data-show="#clr" data-tip="Joint clearance">Show</button></li>
  <li><b>Check joints:</b> runs the status light on all of them. <button data-show="#btn-check-all" data-tip="Checks all joints">Show</button></li>
</ul>
<h3>Export</h3>
<ul>
  <li>Red joints ask for confirmation.</li>
  <li><b>8 mesh tests</b>: closed parts, faces pointing outward, no self intersection, no degenerate triangles, each part a single solid, intact skin, preserved resolution and file read back. The export only goes out if all of them pass.</li>
  <li>With joints and cuts together, each joint goes in the part where it is.</li>
</ul>
<button data-show="#btn-export" data-tip="Exports everything at once">Show the Export button</button>
<h3>After exporting</h3>
<ul>
  <li><b>Download 3MF</b> (the main one, with parts and colors), <b>Assembled STL</b>, <b>Everything (.zip)</b>, the list of separate STLs and <b>Open folder in Finder</b>.</li>
  <li>In the top bar, <b>On the plate</b> shows the parts lying on the build plate, with the outline of each plate; <b>Assembled</b> goes back.</li>
  <li><b>Painting / By part</b> toggles between the applied colors and one color per part.</li>
</ul>
<h3>Position on the plate and supports</h3>
<ul>
  <li>Each cut part goes on the build plate in the position that needs the least support, with more contact area and without standing tall and unstable. The fit stands upright when possible (round hole and pin). E.g.: pants with a flat-top fit print upside down, resting on it.</li>
  <li>The old position (cut face on the plate) stays when the new one is not clearly better.</li>
  <li>The main body and the articulated body stand as in the model; for them you only get the report.</li>
  <li>The <b>On the plate: position and supports</b> report shows, per part, the estimated support area (PLA: face pointing down more than 45° from the wall) and the contact area. 🧱 indicates when to use a brim on that part.</li>
  <li>Turn on elephant foot compensation in the slicer: fits on the plate face then do not bind.</li>
</ul>
<h3>File mesh</h3>
<p>Each STL is checked the way the slicer reads it (in float32), with the coordinates on a fixed grid of 2<sup>-17</sup> mm (the same point always becomes the same number, also on the face resting on the bed): closed, no edges with 3 or more faces and no degenerate triangles. Where two surfaces of a part touch at a point or along an edge (a lock of hair resting on the forehead, cut right at the contact), the app separates them by a few thousandths of a mm, without changing the shape or the colors; triangles that collapse are removed. This applies to every file: cut by color, free cut, joints and the assembled 3MF. The report shows <b>File mesh ✅</b> or the part with a problem.</p>
<p>Full list: <a data-go="arquivos">Generated files</a>.</p>`,
    },
    {
      id: 'arquivos', grupo: 'Step by step', titulo: 'Generated files', icone: '🗂', secao: 's-exp',
      html: `
<p>Each export creates a <code>&lt;model&gt;_&lt;date&gt;/</code> folder in the output folder.</p>
<h3>Joints only</h3>
<ul>
  <li><code>_cores.3mf</code> (painted) or <code>_flexi.3mf</code>: the articulated body with the colors.</li>
  <li><code>_flexi.stl</code>: assembled, without colors.</li>
  <li><code>pecas/</code>: one STL per part.</li>
  <li><code>placas/</code>: one 3MF per plate of the chosen printer.</li>
  <li><code>relatorio.txt</code> and a backup OBJ + MTL when painted.</li>
</ul>
<h3>Cuts only (parts by color or free cut)</h3>
<ul>
  <li><code>_partes.3mf</code>: each part lying flat and spread out on the build plate, on its own filament.</li>
  <li><code>_montado.3mf</code>: the assembled parts, for checking.</li>
  <li><code>pecas/</code>, <code>placas/</code> and <code>LEIA.txt</code> (report and assembly).</li>
</ul>
<h3>Joints and cuts</h3>
<ul>
  <li><code>_tudo.3mf</code>: the whole articulated body (the joints stay in place) and the cut parts separated beside it.</li>
  <li>The joint files, <code>articulado_N/</code> when there is more than one articulated part, and <code>pecas_por_cor/</code>.</li>
</ul>
<p>In every case: <code>&lt;model&gt;.flexiproj</code> with the full project.</p>
<p>In Bambu Studio or OrcaSlicer, open the 3MF: each object already points to its filament.</p>`,
    },
    {
      id: 'calibracao', grupo: 'Step by step', titulo: 'Clearance calibration', icone: '📏', secao: 's-exp',
      html: `
<p>The right clearance depends on the printer and the filament. The coupon tests 6 clearances with the same cut piece and scale as the selected joint.</p>
<ul class="hl-check" data-id="calibracao">
  <li>Select a joint and open <b>Clearance calibration</b> in the Export tab.</li>
  <li>Click <b>Generate calibration coupon</b> and print it.</li>
  <li>Pick the <b>smallest</b> clearance at which the part turns without sticking and is not loose.</li>
  <li>Type that value in <b>Joint clearance</b>.</li>
</ul>
<button data-show="#btn-cupom" data-tip="Generates the coupon (in Clearance calibration)">Show</button>`,
    },

    // ------------------------------------------------------------------ Workflows
    {
      id: 'fluxo-animal', grupo: 'Workflows', titulo: 'Flexi animal from scratch', icone: '🐾',
      html: `
<p>For one-piece articulated animals and creatures. Check off each step as you go; the checkmarks are saved.</p>
<ul class="hl-check" data-id="fluxo-animal">
  <li>Create the animal with the prompts in the Model tab (optional) and generate the 3D model.</li>
  <li>Open the model and check the size in Adjust size and base.</li>
  <li>Click <b>Suggest joints</b> and adjust: neck, legs and tail.</li>
  <li>Change the cut piece where it makes sense (Swivel on the legs, Anchor on the tail).</li>
  <li><b>Check joints</b> until all are green, or yellow with an acceptable reason.</li>
  <li>Paint eyes, nose and details (optional).</li>
  <li>Choose the printer and export.</li>
  <li>Open the 3MF in the slicer and print without supports.</li>
</ul>`,
    },
    {
      id: 'fluxo-humano', grupo: 'Workflows', titulo: 'Human figure', icone: '🥋',
      html: `
<p>AI figures have no sharp edge where the hair or sleeve ends: the bucket leaks. Use the line.</p>
<ul class="hl-check" data-id="fluxo-humano">
  <li>Open the model (a textured GLB comes already painted).</li>
  <li><b>Line (L)</b> along the hairline, at the neck or collar, at the cuffs and at the pant hem.</li>
  <li>Paint inside: hair, face skin, hands and feet.</li>
  <li><b>Split by color</b> with the Automatic type.</li>
  <li>Parts preview: check each area's status light.</li>
  <li>Add a pin to the face and hair if you want a firm fit.</li>
  <li>If the automatic cut does not separate a part (an arm fused to the body, the head held by the braids), use <b>Free cut</b> (Cuts tab): draw the line and choose the fit.</li>
  <li>Export: the parts come out separated on the build plate.</li>
</ul>`,
    },
    {
      id: 'fluxo-ia', grupo: 'Workflows', titulo: 'Textured AI model', icone: '🤖',
      html: `
<ul class="hl-check" data-id="fluxo-ia">
  <li>Export from Meshy, Tripo or similar as GLB (or a .zip with OBJ and texture).</li>
  <li>Open it in the app: automatic repair fixes small defects and the painting comes out ready.</li>
  <li>In the Texture colors box, adjust the number of filaments and clean up specks.</li>
  <li>Touch up with brush or line.</li>
  <li>Continue with joints, cuts or both.</li>
</ul>
<p>Very large files (more than 1 million triangles) take up to 1 minute to open and each cut takes longer, because the mesh is kept whole (print quality comes first).</p>`,
    },
    {
      id: 'fluxo-multicor', grupo: 'Workflows', titulo: 'Multicolor without AMS (parts by color only)', icone: '🧩',
      html: `
<p>To print each color separately and assemble, without swapping filament during the print.</p>
<ul class="hl-check" data-id="fluxo-multicor">
  <li>Paint the parts in different colors.</li>
  <li>Split by color: check the areas and choose the types.</li>
  <li>Add pins to make alignment easier during assembly.</li>
  <li>Export without joints: <code>_partes.3mf</code> holds the parts separated on the build plate.</li>
  <li>Print each color and glue (0.3 mm clearance) or press fit (0.10 to 0.15 mm).</li>
</ul>`,
    },

    // ------------------------------------------------------------------ Reference
    {
      id: 'visualizacao', grupo: 'Reference', titulo: 'View and theme', icone: '👁',
      html: `
<ul>
  <li><b>Orbit:</b> left button. <b>Pan the view:</b> right button. <b>Zoom:</b> wheel, zooming toward the cursor.</li>
  <li><b>Double-click on the model:</b> the view orbits and zooms around that point (neck, hand, detail).</li>
  <li>While painting the left button paints: orbit with the right button or Space + drag.</li>
  <li><b>Camera:</b> 3D, Top, Side and Joint.</li>
  <li><b>Section:</b> a plane that cuts the view at the selected joint; the slider changes its position.</li>
  <li><b>Overhang:</b> highlights in red what prints in mid air. The color comes with the warning on the status light.</li>
</ul>
<h3>Theme</h3>
<p>In the header: ☀ light, A automatic (follows macOS) and ☾ dark. Your choice is saved. <button data-show="#theme-seg" data-tip="Light, automatic or dark theme">Show</button></p>`,
    },
    {
      id: 'claude', grupo: 'Reference', titulo: 'Control by Claude (MCP)', icone: '🤖',
      html: `
<p>Claude can see and operate the app for you: look at the 3D view, rotate the camera, click and drag in the view, press shortcuts and buttons, run the parts preview and read the messages. It lets Claude diagnose a cut that failed or carry out a sequence of steps.</p>
<ul class="hl-check" data-id="claude-mcp">
  <li>At the top of the app, click <b>🤖</b> and turn on <b>Allow Claude to control the app</b>. The button then shows <b>🤖 ●</b>. <button data-show="#btn-mcp" data-tip="Control by Claude">Show</button></li>
  <li>Click <b>Register in Claude Desktop</b> (only once). The app adds EFC3D to the Claude Desktop configuration and keeps a copy of the previous one (<code>.bak</code>).</li>
  <li>Quit and reopen Claude Desktop. The EFC3D tools become available to Claude.</li>
</ul>
<h3>What Claude can do</h3>
<table class="t">
  <tr><th>Tool</th><th>What for</th></tr>
  <tr><td>status, estado, ler_tela</td><td>See the model, the mode, the cuts, the status lights and the messages.</td></tr>
  <tr><td>captura, camera</td><td>See the 3D view and turn the camera (front, back, side, top, zoom).</td></tr>
  <tr><td>clicar, arrastar, mover_mouse, tecla</td><td>Use the view as you would: Line points, brush, bucket, eraser, Enter, ⌘Z.</td></tr>
  <tr><td>clicar_botao, preencher</td><td>Press buttons and change sidebar fields.</td></tr>
  <tr><td>abrir_modelo, previa_pecas</td><td>Open a file and run the parts preview.</td></tr>
  <tr><td>executar_js</td><td>Advanced diagnostics inside the window.</td></tr>
</table>
<p>With control turned off, no command runs. Everything stays on your computer: the app only accepts local connections.</p>
<p class="tipbox">🩺 When a free cut fails, the app saves the cut in <code>EFC3D/ultimo_corte_falho.json</code> for analysis.</p>`,
    },
    {
      id: 'atalhos', grupo: 'Reference', titulo: 'Keyboard shortcuts', icone: '⌨',
      html: `
<p><input type="search" class="hl-filter" placeholder="Filter shortcuts…" aria-label="Filter shortcuts"></p>
<table class="t hl-filterable">
  <tr><th>Key</th><th>Action</th><th>Where</th></tr>
  <tr><td><kbd>⌘O</kbd></td><td>Open model or project</td><td>general</td></tr>
  <tr><td><kbd>⌘S</kbd></td><td>Save project</td><td>general</td></tr>
  <tr><td><kbd>⇧⌘S</kbd></td><td>Save as</td><td>general</td></tr>
  <tr><td><kbd>?</kbd> or <kbd>⌘/</kbd></td><td>Open this help</td><td>general</td></tr>
  <tr><td><kbd>Esc</kbd></td><td>Close help or menu, or cancel the action</td><td>general</td></tr>
  <tr><td><kbd>A</kbd></td><td>All tool</td><td>joints</td></tr>
  <tr><td><kbd>M</kbd> or <kbd>W</kbd></td><td>Move</td><td>joints</td></tr>
  <tr><td><kbd>R</kbd> or <kbd>E</kbd></td><td>Rotate</td><td>joints</td></tr>
  <tr><td><kbd>S</kbd></td><td>Scale</td><td>joints</td></tr>
  <tr><td><kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd></td><td>Nudge 0.5 mm (Shift: 0.1 mm)</td><td>joints</td></tr>
  <tr><td><kbd>PageUp</kbd> <kbd>PageDown</kbd></td><td>Move up and down</td><td>joints</td></tr>
  <tr><td>Shift while rotating</td><td>15° steps</td><td>joints</td></tr>
  <tr><td>Option + wheel</td><td>Joint scale / brush size</td><td>joints and painting</td></tr>
  <tr><td><kbd>Delete</kbd> or <kbd>Backspace</kbd></td><td>Delete the selected item (joint, painted area, part by color, cut)</td><td>lists</td></tr>
  <tr><td><kbd>⌘Z</kbd></td><td>Bring back the last deleted item</td><td>lists</td></tr>
  <tr><td><kbd>B</kbd></td><td>Brush</td><td>painting</td></tr>
  <tr><td><kbd>F</kbd></td><td>Bucket</td><td>painting</td></tr>
  <tr><td><kbd>H</kbd></td><td>Height band</td><td>painting</td></tr>
  <tr><td><kbd>L</kbd> or <kbd>C</kbd></td><td>Line (outline)</td><td>painting</td></tr>
  <tr><td><kbd>E</kbd></td><td>Eraser</td><td>painting and free cut</td></tr>
  <tr><td><kbd>Enter</kbd></td><td>Finish painting (no line in progress)</td><td>painting</td></tr>
  <tr><td><kbd>1</kbd> to <kbd>9</kbd></td><td>Pick the color</td><td>painting</td></tr>
  <tr><td><kbd>[</kbd> <kbd>]</kbd></td><td>Shrink and enlarge the brush</td><td>painting</td></tr>
  <tr><td><kbd>⌘Z</kbd></td><td>Undo painting; with a line in progress, undoes only its last point</td><td>painting</td></tr>
  <tr><td>Shift + click</td><td>Erase (back to color 1) / To Z in the band</td><td>painting</td></tr>
  <tr><td>Space + drag</td><td>Orbit the view</td><td>painting</td></tr>
  <tr><td><kbd>Enter</kbd></td><td>Close the line</td><td>painting line</td></tr>
  <tr><td><kbd>Backspace</kbd></td><td>Undo the last point</td><td>painting line</td></tr>
  <tr><td><kbd>Esc</kbd></td><td>Clear the line in progress / exit painting</td><td>painting line</td></tr>
  <tr><td><kbd>L</kbd> <kbd>B</kbd> <kbd>F</kbd></td><td>Line, brush and bucket</td><td>free cut</td></tr>
  <tr><td><kbd>Enter</kbd></td><td>Close the line; with no line in progress, finish marking</td><td>free cut</td></tr>
  <tr><td><kbd>Backspace</kbd></td><td>Undo the last point of the line</td><td>free cut</td></tr>
  <tr><td><kbd>Esc</kbd></td><td>Clear the line in progress; with no line, finish</td><td>free cut</td></tr>
  <tr><td><kbd>⌘Z</kbd></td><td>With a line in progress, undoes only its last point (lines already closed stay); with no line, undoes the last marking</td><td>free cut</td></tr>
  <tr><td>Shift</td><td>Unmark with brush and bucket</td><td>free cut</td></tr>
</table>`,
    },
    {
      id: 'impressoras', grupo: 'Reference', titulo: 'Printers and plates', icone: '🖨', secao: 's-exp',
      html: `
<table class="t">
  <tr><th>Printer</th><th>Build plate (mm)</th><th>Height (mm)</th></tr>
  <tr><td>Bambu Lab A1 mini</td><td>180 × 180</td><td>180</td></tr>
  <tr><td>Bambu Lab A1</td><td>256 × 256</td><td>256</td></tr>
  <tr><td>Bambu Lab P1S / P1P / X1C</td><td>256 × 256</td><td>256</td></tr>
  <tr><td>Bambu Lab H2D</td><td>350 × 320</td><td>325</td></tr>
  <tr><td>Prusa MK4 / MK4S</td><td>250 × 210</td><td>220</td></tr>
  <tr><td>Creality Ender 3 V2 / V3</td><td>220 × 220</td><td>250</td></tr>
  <tr><td>Creality K1 / K1C</td><td>220 × 220</td><td>250</td></tr>
  <tr><td>Creality K2</td><td>260 × 260</td><td>260</td></tr>
  <tr><td>Creality K2 Pro</td><td>300 × 300</td><td>300</td></tr>
  <tr><td>Creality K2 Plus</td><td>350 × 350</td><td>350</td></tr>
  <tr><td>Custom</td><td colspan="2">enter X, Y and height</td></tr>
</table>
<h3>How plates are laid out</h3>
<ul>
  <li>5 mm margin from the edge and 5 mm between parts; largest first, in rows.</li>
  <li>A part that only fits when rotated 90° is rotated.</li>
  <li>The articulated body is always a single object, so the joints stay in place.</li>
  <li>A part larger than the build plate gets its own plate and a warning: reduce the size or cut it into more parts.</li>
</ul>`,
    },
    {
      id: 'desempenho', grupo: 'Reference', titulo: 'Performance and requirements', icone: '⚡',
      html: `
<p>EFC3D draws the 3D view on the graphics card (WebGL). When the system does not hand the card to the app, drawing falls back to the processor: orbiting the model, the pen and the brush become slow. When that happens, the view shows <b>⚠ 3D without graphics card</b> in its corner.</p>
<h3>Requirements</h3>
<table class="t">
  <tr><th></th><th>Minimum</th><th>Recommended</th></tr>
  <tr><td>System</td><td>Windows 10 or 11 (64-bit) with WebView2; macOS 11</td><td>Windows 11; macOS 13 or newer</td></tr>
  <tr><td>Processor</td><td>4 cores, 64-bit (8th gen Intel Core i5, AMD Ryzen 3000, 2017 Intel Mac, any Apple Silicon)</td><td>6 cores or more, or Apple Silicon</td></tr>
  <tr><td>Memory</td><td>8 GB</td><td>16 GB</td></tr>
  <tr><td>Graphics</td><td>3D acceleration on and an up-to-date driver; integrated graphics are fine (Intel UHD 620, Iris Xe, AMD Radeon Vega)</td><td>Recent integrated or dedicated (NVIDIA or AMD)</td></tr>
  <tr><td>Screen</td><td>1366 × 768</td><td>1920 × 1080</td></tr>
</table>
<p>Measured: a 130 thousand triangle model with 5 cuts uses about 0.5 GB in the engine while exporting. Larger models need more memory and more cutting time.</p>
<h3>If "3D without graphics card" shows up or the view is slow</h3>
<ul>
  <li><b>Remote access or virtual machine</b> (Remote Desktop, AnyDesk, Parallels, VirtualBox): they almost always draw without the card. Use the app directly on the computer.</li>
  <li><b>Graphics driver:</b> update it from the Intel, AMD or NVIDIA website. On Windows, "Microsoft Basic Display Adapter" in Device Manager means the driver is missing.</li>
  <li><b>Laptop with two graphics cards (Windows):</b> Settings › System › Display › Graphics › EFC3D › High performance. The app already asks WebView2 for the high performance card.</li>
  <li><b>Power saving mode</b> on battery slows the card and the processor: plug in or choose Best performance.</li>
</ul>
<p>Even without the card the app draws lighter: when idle the scene is not redrawn for nothing; while orbiting or painting the view resolution drops until it is smooth and returns to full sharpness when the mouse stops. The card in use is shown in <a data-go="sobre">About and maintenance</a>.</p>`,
    },
    {
      id: 'problemas', grupo: 'Reference', titulo: 'Troubleshooting', icone: '🩺',
      html: `
<details><summary>The model does not open or gives a mesh error</summary><p>Automatic repair fixes small defects. If it still fails, the file has large defects: export it again from the generator as STL or GLB, or repair it in Bambu Studio (Fix model) and open it again.</p></details>
<details><summary>Red joint</summary><p>Click the joint and read the reason in the panel. The most common: cross section too small for the cut piece (use Fit size to location or a smaller piece), thin skin (move it away from the surface) or overlap with another joint or fit.</p></details>
<details><summary>"Load failed" appears when opening a model</summary><p>The window lost the app's engine (for example, after an update installed with the app open). Quit the app (⌘Q) and open it again. Since 1.16 the new version closes the old one automatically.</p></details>
<details><summary>The bucket paints too much</summary><p>Lower the angle limit, switch Direction to Creases or use the Line (L), made for organic models.</p></details>
<details><summary>I opened the project and the colors or cuts are gone</summary><p>In version 1.4, when exporting joints and cuts together, the .flexiproj in the export folder had only the articulated body. Open the project you saved with ⌘S (see Recent). From 1.5 on, every export saves the full project.</p></details>
<details><summary>"The painting changed since the areas were chosen"</summary><p>Open Split by color again: each area's options come back automatically and the list is rebuilt with the current painting.</p></details>
<details><summary>"The model's painting is empty"</summary><p>The painting was erased after the areas were chosen (Clear painting, or Delete on an area in Painted areas), so there are no color parts to split. To bring it back: in the Colors tab, ⌘Z (Ctrl+Z) undoes the painting; outside painting, ⌘Z brings back an area deleted from the list. Free cuts or joints are still exported.</p></details>
<details><summary>Part does not fit on the build plate</summary><p>Change the printer in the Export tab, reduce the size in Adjust size and base or split the large part into more parts.</p></details>
<details><summary>The parts do not move after printing</summary><p>The clearance is too small for your printer. Print the <a data-go="calibracao">calibration coupon</a> and increase the clearance.</p></details>
<details><summary>Windows: the installer closes or says it could not find Python</summary><p>Install Python 3.12 from python.org checking "Add python.exe to PATH" (or accept the winget installation the installer offers) and run <code>instalar_windows.bat</code> again. If Windows warns that the file came from the internet, click More info › Run anyway.</p></details>
<details><summary>Windows: the app opened in the browser and not in its own window</summary><p>The app's own window uses Microsoft WebView2, which ships with up-to-date Windows 10 and 11. Without it the app opens in Edge in app mode and works the same. To quit in that mode, close Edge and use Task Manager to end the EFC3D pythonw process, or restart the computer.</p></details>
<details><summary>Where is the error log?</summary><p><code>~/EFC3D/app.log</code>. Send this file along when you report a problem.</p></details>`,
    },
    {
      id: 'novidades', grupo: 'Reference', titulo: "What's new", icone: '✨',
      html: '<div class="hl-novidades"></div>',
    },
    {
      id: 'sobre', grupo: 'Reference', titulo: 'About and maintenance', icone: 'ℹ',
      html: `
<p><b>EFC3D</b> · app <span class="hl-appver"></span> · documentation <span class="hl-docver"></span>, updated on <span class="hl-docdate"></span>.</p>
<ul>
  <li>Runs locally: the app's server stays on your computer and nothing is sent to the internet.</li>
  <li>System in use now: <b class="hl-sys"></b>.</li>
  <li>Graphics card in use: <b class="hl-gpu"></b> (requirements in <a data-go="desempenho">Performance and requirements</a>).</li>
</ul>
<h3>Available versions</h3>
<table class="t">
  <tr><th>System</th><th>Version</th><th>Install or update</th><th>Uninstall</th></tr>
  <tr><td>🍎 macOS 11 or newer (Apple Silicon or Intel)</td><td class="hl-appver"></td><td>open the <code>.dmg</code> and drag EFC3D to Applications</td><td>drag EFC3D to the Trash</td></tr>
  <tr><td>🪟 Windows 10 or 11 (64-bit)</td><td class="hl-appver"></td><td>run <code>EFC3D-…-windows-instalador.exe</code></td><td>Settings › Apps › EFC3D › Uninstall</td></tr>
</table>
<ul>
  <li>The packages include everything. From source (optional) it requires Python 3.10 to 3.13: <code>bash install.sh</code> on Mac or <code>instalar_windows.bat</code> on Windows.</li>
  <li>Processor, memory and graphics card: <a data-go="desempenho">Performance and requirements</a>.</li>
  <li>Generated files go to <code>Documents/EFC3D/saidas</code> (Documentos on Windows). Uninstalling does not delete this folder.</li>
  <li>Error log: <code>EFC3D/app.log</code> in the user folder.</li>
</ul>
<h3>How this documentation is maintained</h3>
<p>It lives in its own file (<code>web/ajuda.js</code>) and is updated with every version, together with the code. If the documentation version differs from the app version, a warning appears at the top of this window.</p>`,
    },
  ],

  novidades: [
    { versao: '1.58', data: '11/11/2026', itens: [
      'Parts by color: you can now rename the part of each painted area, as with free cuts. Select the area (Cuts tab, Split by color) and type in the Name field. The name goes to the list, the preview, the report and the 3MF, and is saved in the project.',
    ] },
    { versao: '1.57', data: '10/11/2026', itens: [
      'Free cut: the razor is back where it gets it right. Each cut is first tried as a smooth blade (flat face and clean edge, as up to 1.47) and stays that way when the seam lands on the drawn line; otherwise it goes along the skin, with the seam exactly on the line. The socket is now always added at the end, after all the cuts, and no longer goes through a thin piece (the hollow waist and the grooved bands).',
      'Cut along the skin: the edge of the new face is clean. Next to the seam the face follows a surface parallel to the skin, instead of each point moving on its own (the crumbs around the fit).',
      'Cut along the skin: the piece always comes out toward the side where its skin is. Before, on a head already opened by another cut, the ear came out inward: it was smaller than the other one, with a shell shaped face, and occupied the same space as the head.',
      'Free cut: the fit of a cut is also found on the piece that a later cut took from it (the neck taken from the torso has a pin on top and at the bottom).',
      'Free cut: the razor no longer opens a slit in the layer that covers the part. On an arm that goes into a sleeve, the blade went past the arm and cut the sleeve hem; now it is trimmed to the shadow of the piece, and the arm comes out with a smooth face and the sleeve whole.',
      'Free cut: the pin of the fit goes in the direction the piece enters when it does not fit along the axis of the part or would come out thin and crooked, and the two matching parts of a figure (both legs, both cuffs) come out with the same fit.',
    ] },
    { versao: '1.55', data: '10/11/2026', itens: [
      'Free cut with many cuts: a cut drawn on a piece that came from another cut now runs after it, in the right order. Before, a smaller cut could run first and the next one lost its piece (on the Santa, the leg stopped coming out).',
      'Free cut: "Part goes into the body (socket)" works again with the cut along the skin. The piece goes 4 mm into the body, with straight walls and the standard pin at the bottom, like the razor socket of earlier versions. The socket is made at the end, after all the cuts, and if it does not fit the joint keeps the pin and the warning says why. Both ears, both arms and both legs now come out with the same fit.',
      'Free cut: a cut drawn on the head next to another piece no longer lands on the wrong piece; the right piece is the one the line touches.',
      'Free cut: fewer teeth on the new face next to the seam.',
    ] },
    { versao: '1.54', data: '09/11/2026', itens: [
      'Fixed: after the painting was erased, exporting kept saying "The painting changed since the areas were chosen", even after opening Split by color again. Now the app says the painting is empty, exports the rest (free cut, joints) and reminds you that ⌘Z in the Colors tab brings the painting back.',
    ] },
    { versao: '1.53', data: '09/11/2026', itens: [
      'Free cut: new shape Plug: straight walls (beta). The area inside the line comes out like the plug of the color cut, with the seam exactly on the line, straight walls, a flat bottom and the same clearance all around (0.3 mm, adjustable). Choose it in Cut shape; it is manual only, and the other cuts do not change.',
      'Free cut: a loose dowel from a cut no longer goes back to the body when the model is an articulated flexi.',
    ] },
    { versao: '1.52', data: '08/11/2026', itens: [
      'Windows and computers without a graphics card run much smoother: the brush and the pen no longer recompile the graphics on every stroke, orbiting the model got up to 3 times faster and an idle view is not redrawn for nothing.',
      'Clicks, the pen and the brush find the point on the model right away, even on models with more than 100 thousand triangles.',
      'When the 3D is drawn without the graphics card, the view adjusts itself to stay smooth and shows the ⚠ 3D without graphics card notice, with what to do. On Windows the app asks for the high performance card.',
      'Help: new Performance and requirements topic, with the minimum and recommended processor, memory and graphics card.',
    ] },
    { versao: '1.51', data: '08/11/2026', itens: [
      'Flexi that is already articulated (print in place): after a cut, the parts that fit into each other stay one piece, assembled and in the model\'s position. Before, the legs and joints went to the bed as loose parts, or ended up in the cut piece.',
    ] },
    { versao: '1.50', data: '08/11/2026', itens: [
      'First public version. The app is now called EFC3D (Easy Flexy and Cuts 3D), for Mac and Windows, with a one-click installer.',
      'Joints: every cut piece is our own (RLA). An old project that used a third-party piece opens with the own joint in the same place, the scale redone and a warning to check it.',
      'Cuts on a piece made by another cut: the source cut always runs first; deleting or modifying the source cut also deletes the cuts drawn on its piece, with a warning first and ⌘Z to undo; if the source cut does not come out, the dependent cuts do not run and the reason is shown.',
      'Color split uses less memory in projects with many areas.',
      'Settings in ~/EFC3D and output in Documents/EFC3D/saidas (if you already used the Flexi Studio folder you keep using it; nothing is deleted).',
    ] },
  ],

  // guided tour: element, title, text
  tour: [
    { alvo: '#file-btn', titulo: 'File', texto: 'Open a model or project, Recent, Save and Save as. ⌘O opens, ⌘S saves.' },
    { alvo: '#tabs', titulo: 'Steps', texto: 'Like in Fusion 360: each step is a tab. 1 Model, 2 Joints, 3 Colors, 4 Cuts and 5 Export.' },
    { alvo: '#ribbon', titulo: 'Toolbar ribbon', texto: 'The commands of the active tab, in groups. The lit button is the mode in use (painting, marking a cut, moving or rotating the joint).' },
    { alvo: '#browser', titulo: 'Browser', texto: 'The project tree: joints, areas, cuts, planes and parts. Click to select; 👁 shows and hides.' },
    { alvo: '#viewcube', titulo: 'View cube', texto: 'Click a face or a corner to see the model from there. ⌂ returns to the home view.' },
    { alvo: '#navbar', titulo: 'Navigation', texto: 'Orbit, Pan, Fit and Home; the views; Display (section, overhang, grid) and the Mouse scheme. With the Fusion default, the middle button pans and Shift + middle button orbits.' },
    { alvo: '#viewbar', titulo: 'View', texto: 'Model, Parts preview and Exported. After exporting: Assembled or On the plate.' },
    { alvo: '#side', titulo: 'Command panel', texto: 'The tab\'s options: lists, the editor for the selected item and the reports.' },
    { alvo: '#timeline', titulo: 'Timeline', texto: 'The 5 steps with what has been done in each. Click to go to that step.' },
    { alvo: '#hdr-tools', titulo: 'Help and theme', texto: 'This help lives here (or press ?). Next to it, light, automatic or dark theme.' },
  ],

};
