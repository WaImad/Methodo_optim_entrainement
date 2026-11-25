// page Profil : chiffres clés et courbe de puissance record (notebook de Camilo)
function drawProfil(c) {
  const p = c.profil;
  const liste = document.getElementById('profil-chiffres');
  if (!p) {
    liste.innerHTML = '<li>Pas de profil pour ce cycliste.</li>';
    return;
  }

  liste.innerHTML = `
    <li><b>Profil choisi</b> ${p.profil_choisi}</li>
    <li><b>Classement Valenzuela</b> ${p.profil_valenzuela}</li>
    <li><b>CP</b> ${arrondi(p.cp)} W, ${arrondi(p.cp_wkg, 2)} W/kg</li>
    <li><b>W'</b> ${arrondi(p.w_prime_kj, 1)} kJ</li>
    <li><b>Dérive cardiaque médiane</b> ${arrondi(p.derive_cardiaque_pct, 1)} %</li>`;

  const libelle = d => d < 60 ? `${d} s` : `${d / 60} min`;
  chart('profil-mmp', {
    type: 'line',
    data: {
      labels: p.mmp_durees.map(libelle),
      datasets: [
        { label: 'W/kg', data: p.mmp_wkg, borderColor: COULEURS.bleu, yAxisID: 'y', pointRadius: 3 },
        { label: 'W', data: p.mmp_w, borderColor: COULEURS.gris, yAxisID: 'y1', pointRadius: 3 }
      ]
    },
    options: {
      scales: {
        y: { title: { display: true, text: 'W/kg' } },
        y1: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'W' } }
      }
    }
  });
}
