// page Charge interne et psy : TRIMP et sRPE par semaine, zones de FC, Hooper (script de Zoé)
function drawInterne(c) {
  const i = c.interne;
  document.getElementById('interne-info').textContent =
    `FC max ${i.fc_max} bpm. ${i.nb_seances_fc} séances avec FC sur ${c.n_rides + c.n_other} ` +
    `(les autres n'entrent pas dans le TRIMP). RPE et Hooper : données fictives.`;

  chart('interne-semaine', {
    data: {
      labels: i.semaine,
      datasets: [
        { type: 'bar', label: 'TRIMP Edwards', data: i.trimp_semaine, backgroundColor: COULEURS.orangeClair, yAxisID: 'y' },
        { type: 'line', label: 'sRPE', data: i.srpe_semaine, borderColor: COULEURS.violet, yAxisID: 'y1' }
      ]
    },
    options: {
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { ticks: { maxTicksLimit: 12 } },
        y: { title: { display: true, text: 'TRIMP' } },
        y1: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'sRPE (UA)' } }
      }
    }
  });

  chart('interne-zones', {
    type: 'bar',
    data: {
      labels: ['Z1 50-60 %', 'Z2 60-70 %', 'Z3 70-80 %', 'Z4 80-90 %', 'Z5 90-100 %'],
      datasets: [{ label: 'heures', data: i.zones_fc_min.map(m => m / 60), backgroundColor: COULEURS.orange }]
    },
    options: { plugins: { legend: { display: false } }, scales: { y: { title: { display: true, text: 'heures' } } } }
  });

  chart('interne-hooper', {
    type: 'line',
    data: {
      labels: i.hooper_date,
      datasets: [{ label: 'Hooper', data: i.hooper, borderColor: COULEURS.violet, borderWidth: 1.5 }]
    },
    options: {
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { maxTicksLimit: 12 } }, y: { min: 4, max: 28 } }
    }
  });
}
