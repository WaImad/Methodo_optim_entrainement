// page Évolution : charge quotidienne (TSS) par type de séance et courbes forme / fatigue / fraîcheur
function drawEvolution(c) {
  const d = c.evolution;
  const info = d.info;

  document.getElementById('evolution-info').textContent =
    `Sans puissance, le TSS est estimé par la FC (${info.tss_par_trimp.toFixed(2)} TSS par point de TRIMP Edwards). ` +
    `${info.nb_seances_par_type.autre} séances d'autres sports, ` +
    `${info.nb_seances_sans_donnees} séances sans puissance ni FC comptées à 0.`;

  // chaque courbe dans sa propre pile pour qu'elles ne s'additionnent pas aux barres
  const bar = (label, data, color) => ({ type: 'bar', label, data, backgroundColor: color, stack: 'tss', order: 4 });
  const line = (label, data, color, order) => ({ type: 'line', label, data, borderColor: color, backgroundColor: color, stack: label, order });

  chart('evolution-chart', {
    data: {
      labels: d.date,
      datasets: [
        bar('Vélo', d.tss_velo, COULEURS.gris),
        bar('Vélo, estimé FC', d.tss_velo_fc, COULEURS.bleuClair),
        bar('Autre sport, estimé FC', d.tss_autre, COULEURS.orangeClair),
        line('Forme (CTL)', d.ctl, COULEURS.bleu, 1),
        line('Fatigue (ATL)', d.atl, COULEURS.orange, 2),
        line('Fraîcheur (TSB)', d.tsb, COULEURS.vert, 3)
      ]
    },
    options: {
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { stacked: true, ticks: { maxTicksLimit: 12 } },
        y: { stacked: true, title: { display: true, text: 'TSS' } }
      }
    }
  });
}
