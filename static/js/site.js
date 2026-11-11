/* Shared behaviour for the classifieds site. Loaded after Leaflet. */

// OpenStreetMap's tile policy requires a Referer header and attribution
// (https://operations.osmfoundation.org/policies/tiles/). Django's default
// Referrer-Policy is "same-origin", which strips the Referer from tile requests,
// so the tile layer sends the site's origin explicitly.
function addBaseLayer(map) {
  return L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    referrerPolicy: 'strict-origin-when-cross-origin',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
}

// Photo viewer: click a [data-lightbox] link to view it full size; arrow keys or
// buttons step through, Esc or clicking the backdrop closes.
(function () {
  const links = Array.from(document.querySelectorAll('[data-lightbox]'));
  if (!links.length) return;
  let box = null, index = 0;

  function show(i) {
    index = (i + links.length) % links.length;
    const img = box.querySelector('img');
    img.src = links[index].href;
    img.alt = links[index].querySelector('img').alt;
    box.querySelector('.count').textContent = `${index + 1} / ${links.length}`;
  }
  function close() {
    box.remove();
    box = null;
    document.removeEventListener('keydown', onKey);
    document.body.style.overflow = '';
    links[index].focus();
  }
  function onKey(e) {
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') show(index - 1);
    else if (e.key === 'ArrowRight') show(index + 1);
    else if (e.key === 'Tab') {
      // Keep keyboard focus inside the open viewer (it's a modal dialog).
      const buttons = Array.from(box.querySelectorAll('button'));
      const at = buttons.indexOf(document.activeElement);
      const next = at === -1 ? 0 : (at + (e.shiftKey ? -1 : 1) + buttons.length) % buttons.length;
      buttons[next].focus();
      e.preventDefault();
    }
  }
  function open(i) {
    box = document.createElement('div');
    box.className = 'lightbox';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.innerHTML = '<img><span class="count"></span>' +
      '<button class="close" aria-label="Close">×</button>' +
      (links.length > 1 ? '<button class="prev" aria-label="Previous photo">‹</button>' +
                          '<button class="next" aria-label="Next photo">›</button>' : '');
    box.addEventListener('click', e => {
      if (e.target.classList.contains('prev')) show(index - 1);
      else if (e.target.classList.contains('next')) show(index + 1);
      else if (e.target.tagName !== 'IMG') close();
    });
    document.body.appendChild(box);
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', onKey);
    show(i);
    box.querySelector('.close').focus();
  }
  links.forEach((link, i) => link.addEventListener('click', e => { e.preventDefault(); open(i); }));
})();

// Ad form: previews for newly chosen photos, and dim photos ticked for removal.
(function () {
  const input = document.querySelector('.dropzone input[type=file]');
  if (input) {
    const zone = input.closest('.dropzone');
    const previews = document.getElementById('new-photo-previews');
    let urls = [];
    input.addEventListener('change', () => {
      urls.forEach(URL.revokeObjectURL);
      urls = Array.from(input.files).map(f => URL.createObjectURL(f));
      previews.innerHTML = urls.map(u =>
        `<div class="thumb"><span class="new-badge">New</span><img src="${u}" alt=""></div>`).join('');
    });
    ['dragenter', 'dragover'].forEach(t => zone.addEventListener(t, () => zone.classList.add('dragging')));
    ['dragleave', 'drop'].forEach(t => zone.addEventListener(t, () => zone.classList.remove('dragging')));
  }
  document.querySelectorAll('.thumb input[name=remove_images]').forEach(box => {
    const sync = () => box.closest('.thumb').classList.toggle('marked', box.checked);
    box.addEventListener('change', sync);
    sync();
  });
})();

// Ad page: map with the ad's (rounded) location.
(function () {
  const el = document.querySelector('#map[data-lat][data-lng]');
  if (!el) return;
  const ll = [parseFloat(el.dataset.lat), parseFloat(el.dataset.lng)];
  const map = L.map(el, { scrollWheelZoom: false }).setView(ll, 13);
  addBaseLayer(map);
  L.marker(ll).addTo(map);
})();

// Post/edit form: click the map (or use the browser's location) to set the pin.
(function () {
  const latInput = document.getElementById('id_latitude');
  const lngInput = document.getElementById('id_longitude');
  const el = document.getElementById('map');
  if (!latInput || !lngInput || !el) return;
  const map = L.map(el).setView([20, 0], 2);
  addBaseLayer(map);
  let marker = null;

  function place(lat, lng, zoom) {
    latInput.value = lat.toFixed(3);  // stored rounded to about 100 m anyway
    lngInput.value = lng.toFixed(3);
    if (marker) marker.setLatLng([lat, lng]); else marker = L.marker([lat, lng]).addTo(map);
    if (zoom) map.setView([lat, lng], zoom);
  }

  if (latInput.value && lngInput.value) place(parseFloat(latInput.value), parseFloat(lngInput.value), 13);
  map.on('click', e => place(e.latlng.lat, e.latlng.lng));
  document.getElementById('use-location').addEventListener('click', () => {
    if (!navigator.geolocation) { alert('Geolocation is not supported by your browser.'); return; }
    navigator.geolocation.getCurrentPosition(
      pos => place(pos.coords.latitude, pos.coords.longitude, 14),
      () => alert('Could not get your location.')
    );
  });
})();

// Search bar: typing a place clears coordinates; the locate button searches near you.
(function () {
  const near = document.getElementById('id_near');
  const button = document.getElementById('near-me');
  if (!near || !button) return;
  const lat = document.getElementById('id_lat');
  const lng = document.getElementById('id_lng');
  near.addEventListener('input', () => { lat.value = ''; lng.value = ''; });
  button.addEventListener('click', () => {
    const label = button.querySelector('span');
    if (!navigator.geolocation) { alert('Geolocation is not supported by your browser.'); return; }
    label.textContent = 'Finding your location…';
    button.classList.add('busy');
    navigator.geolocation.getCurrentPosition(pos => {
      near.value = '';
      lat.value = pos.coords.latitude.toFixed(3);
      lng.value = pos.coords.longitude.toFixed(3);
      const radius = document.getElementById('id_radius');
      if (!radius.value) radius.value = 15;
      button.form.submit();
    }, () => {
      label.textContent = 'Use my current location';
      button.classList.remove('busy');
      alert('Could not get your location.');
    });
  });
})();

// Theme switch: flip light/dark instantly and remember it in the `theme` cookie, which the
// server reads to render <html data-theme> on the next page (see classifieds/theme.py).
(function () {
  const form = document.querySelector('.theme-toggle');
  if (!form) return;
  const button = form.querySelector('button');
  const root = document.documentElement;
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  const colors = { light: '#0f5c4d', dark: '#111513' };
  const current = () => root.dataset.theme || (system.matches ? 'dark' : 'light');

  function render() {
    const theme = current();
    const next = theme === 'dark' ? 'light' : 'dark';
    button.value = next;
    button.dataset.current = theme;
    button.setAttribute('aria-label', `Switch to ${next} theme`);
    button.title = `Switch to ${next} theme`;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = colors[theme];
  }

  form.addEventListener('submit', e => {
    e.preventDefault();
    const theme = button.value;
    root.dataset.theme = theme;
    const secure = location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = `theme=${theme}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
    render();
  });
  system.addEventListener('change', render);
  render();
})();
