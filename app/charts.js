// un graphe par canvas : on détruit l'ancien avant de redessiner (changement de cycliste)
const charts = {};

Chart.defaults.animation = false;
Chart.defaults.elements.point.radius = 0;
Chart.defaults.elements.line.borderWidth = 2;

function chart(id, config) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), config);
}

const COULEURS = {
  bleu: '#2a78d6', orange: '#eb6834', vert: '#1baf7a', violet: '#6250d6',
  gris: '#bbb', bleuClair: '#9cc3ee', orangeClair: '#f2b48f'
};

const arrondi = (v, n = 0) => v == null ? '-' : v.toFixed(n);
