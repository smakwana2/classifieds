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
