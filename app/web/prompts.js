// Prompts used in ChatGPT to create the model images, kept here so the whole process is in one
// place. Texts are the user's own; [ANIMAL] is replaced by the animal typed in the field.
export const PROMPT1 = `Create 1 image of a 3D toy figure of a chibi [ANIMAL], seen from the front, camera exactly on the center line of the animal, elevated 45 degrees above the ground, looking down at it.

SYMMETRY: the figure is perfectly bilaterally symmetrical. Left and right sides are exact mirror images: same ears, same eyes, same legs in identical mirrored positions. Body straight along the center line, tail straight behind on the center line. No tilt, no turn, no asymmetric pose.

STYLE: chibi kawaii proportions. Oversized round head about 40% of the total body length, short chubby body, short thick stubby legs, big fluffy tail, large cute eyes. Smooth matte unpainted plastic, one uniform color, no texture, no fur strands, no accessories, no base.

THE FIGURE: a solid one-piece sculpted toy, smooth continuous body with no segments, no joints, no grooves, no seams.

POSE: lying PRONE, belly down, flat on the ground. Head resting on the ground, chin touching the floor, face pointing forward toward the camera. LEGS: the front legs come out of the shoulders BEHIND the head and point straight out sideways at 90 degrees from the body, extending clearly beyond the width of the head. The front paws do NOT touch the head, cheeks or chin and are NOT tucked under the head. The hind legs come out of the hips and point outward and backward at 45 degrees. Clearly visible floor between each leg and the head, the body and the tail. Tail lying flat on the ground, not touching the legs.

SHAPE RULES FOR PRINTING WITHOUT SUPPORTS: flat bottom everywhere, belly, chin, legs and tail all touch the ground, nothing hangs over empty space, no overhang steeper than 45 degrees. Ears solid and thick, triangular, with no hollow inside. Eyes, nose and mouth as low relief. Every leg and the tail at least 5 mm thick at real scale.

Plain light gray background, soft even lighting, no text.`;

export const PROMPT2 = `This is a 3D toy figure. Render this EXACT same object, unchanged, from differents camera and imagens : front, left, rigth and back True orthographic camera, no perspective, same plain light gray background, same lighting, no shadows, no text. Do not change the design, pose, proportions or symmetry.`;

const KEY = 'flexi_prompts_v1';
const $ = (s) => document.querySelector(s);

function load() {
  try { const v = JSON.parse(localStorage.getItem(KEY) || 'null'); if (v && v.p1 && v.p2) return v; } catch (e) {}
  return { p1: PROMPT1, p2: PROMPT2, animal: '' };
}
function save(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} }

async function copyText(t, btn) {
  let ok = false;
  try { await navigator.clipboard.writeText(t); ok = true; } catch (e) {
    const ta = document.createElement('textarea'); ta.value = t; document.body.appendChild(ta); ta.select();
    try { ok = document.execCommand('copy'); } catch (e2) {} ta.remove();
  }
  const old = btn.textContent; btn.textContent = ok ? 'Copiado ✓' : 'Não deu para copiar'; setTimeout(() => { btn.textContent = old; }, 1600);
}

export function initPrompts() {
  const st = load();
  const box = $('#prompt-box');
  const animal = $('#pr-animal'), t1 = $('#pr-1'), t2 = $('#pr-2'), edit = $('#pr-edit');
  animal.value = st.animal || '';
  const fill = () => {
    const a = animal.value.trim() || '[ANIMAL]';
    if (edit.checked) { t1.value = st.p1; t2.value = st.p2; }
    else { t1.value = st.p1.split('[ANIMAL]').join(a); t2.value = st.p2.split('[ANIMAL]').join(a); }
    t1.readOnly = t2.readOnly = !edit.checked;
    box.classList.toggle('editing', edit.checked);
  };
  animal.addEventListener('input', () => { st.animal = animal.value; save(st); fill(); });
  edit.addEventListener('change', fill);
  t1.addEventListener('input', () => { if (edit.checked) { st.p1 = t1.value; save(st); } });
  t2.addEventListener('input', () => { if (edit.checked) { st.p2 = t2.value; save(st); } });
  $('#pr-copy1').onclick = (e) => { if (!animal.value.trim() && !edit.checked) { animal.focus(); $('#pr-hint').textContent = 'Escreva o animal antes de copiar o prompt 1.'; return; } copyText(t1.value, e.target); };
  $('#pr-copy2').onclick = (e) => copyText(t2.value, e.target);
  $('#pr-reset').onclick = () => { st.p1 = PROMPT1; st.p2 = PROMPT2; save(st); fill(); $('#pr-hint').textContent = 'Textos originais restaurados.'; };
  $('#btn-prompts').onclick = () => { box.classList.toggle('hidden'); fill(); };
  fill();
}
