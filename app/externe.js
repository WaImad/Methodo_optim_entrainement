// page Charge externe : TSS et heures par semaine, temps par zone de puissance (script d'Imad)
function drawExterne(c) {
  const e = c.externe;
  const ftp = Object.entries(e.ftp).map(([a, f]) => `${f} W en ${a}`).join(', ');
  document.getElementById('externe-info').textContent =
    `FTP : ${ftp}. Sorties vélo avec capteur de puissance seulement.`;

  chart('externe-semaine', {
    data: {
      labels: e.semaine,
      datasets: [
        { type: 'bar', label: 'TSS', data: e.tss_semaine, backgroundColor: COULEURS.gris, yAxisID: 'y' },
        { type: 'line', label: 'Heures', data: e.heures_semaine, borderColor: COULEURS.bleu, yAxisID: 'y1' }
      ]
    },
    options: {
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { ticks: { maxTicksLimit: 12 } },
        y: { title: { display: true, text: 'TSS' } },
        y1: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'heures' } }
      }
    }
  });

  // une série par année, les zones en abscisse
  const zones = [...new Set(e.zones.map(z => z.zone))];
  const annees = [...new Set(e.zones.map(z => z.annee))];
  const couleurs = [COULEURS.bleu, COULEURS.orange];
  chart('externe-zones', {
    type: 'bar',
    data: {
      labels: zones,
      datasets: annees.map((a, k) => ({
        label: String(a),
        data: zones.map(z => (e.zones.find(x => x.annee === a && x.zone === z) || {}).pct),
        backgroundColor: couleurs[k % couleurs.length]
      }))
    },
    options: { scales: { y: { title: { display: true, text: '% du temps' } } } }
  });
}
