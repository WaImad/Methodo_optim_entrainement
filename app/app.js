const cyclists = window.DATA.cyclists;
const select = document.getElementById('cyclist');
const pages = document.querySelectorAll('main section');
const links = document.querySelectorAll('nav a');

// choix du cycliste
cyclists.forEach(c => select.add(new Option(c.label, c.id)));

let saved = null;
try { saved = localStorage.getItem('cyclist'); } catch (e) {}
select.value = cyclists.some(c => c.id === saved) ? saved : cyclists[0].id;

select.addEventListener('change', () => {
  try { localStorage.setItem('cyclist', select.value); } catch (e) {}
  render();
});

function current() {
  return cyclists.find(c => c.id === select.value);
}

// chaque page redessine ses graphes ici à partir de current()
function render() {
  const c = current();
  document.querySelector('.who').textContent =
    `${c.weight_kg} kg, ${c.years.join(' et ')}, ${c.n_rides} sorties vélo, ${c.n_other} autres séances`;
  document.querySelector('.print-name').textContent = `${c.label} (${c.weight_kg} kg)`;
  document.querySelector('.print-date').textContent = 'Édité le ' + new Date().toLocaleDateString('fr-FR');

  drawProfil(c);
  drawExterne(c);
  drawInterne(c);
  drawEvolution(c);
}

// navigation : une page par section
function show() {
  let id = location.hash.slice(1);
  if (!document.getElementById(id)) id = pages[0].id;

  pages.forEach(p => p.hidden = p.id !== id);
  links.forEach(a => a.classList.toggle('active', a.hash === '#' + id));
}

// export PDF : on affiche toutes les pages, on redimensionne les graphes, puis l'impression du navigateur
// ("Enregistrer au format PDF" dans la fenêtre d'impression)
function preparerImpression() {
  document.body.classList.add('printing');
  Object.values(charts).forEach(ch => ch.resize());
}

function finirImpression() {
  document.body.classList.remove('printing');
  Object.values(charts).forEach(ch => ch.resize());
}

document.getElementById('pdf').addEventListener('click', () => {
  preparerImpression();
  setTimeout(() => window.print(), 200);
});
window.addEventListener('beforeprint', preparerImpression);
window.addEventListener('afterprint', finirImpression);

window.addEventListener('hashchange', show);
show();
render();
