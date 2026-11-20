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
    `${c.weight_kg} kg, ${c.years.join(' et ')}, ${c.n_rides} sorties`;
}

// navigation : une page par section
function show() {
  let id = location.hash.slice(1);
  if (!document.getElementById(id)) id = pages[0].id;

  pages.forEach(p => p.hidden = p.id !== id);
  links.forEach(a => a.classList.toggle('active', a.hash === '#' + id));
}

window.addEventListener('hashchange', show);
show();
render();
