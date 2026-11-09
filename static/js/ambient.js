function initAmbient(effectType, accentColor) {
  const canvas = document.getElementById('ambient-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  let width = canvas.width = window.innerWidth;
  let height = canvas.height = window.innerHeight;
  
  window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  const particles = [];
  const count = effectType === 'stars' ? 90 : 45;
  const color = accentColor || '#8b5cf6';

  for (let i = 0; i < count; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 2 + 1,
      speedX: (Math.random() - 0.5) * 0.6,
      speedY: (Math.random() - 0.5) * 0.6,
      alpha: Math.random() * 0.5 + 0.2
    });
  }

  function render() {
    ctx.clearRect(0, 0, width, height);
    
    if (effectType === 'aurora') {
      const grad = ctx.createLinearGradient(0, 0, width, height);
      grad.addColorStop(0, 'rgba(139, 92, 246, 0.04)');
      grad.addColorStop(0.5, 'rgba(236, 72, 153, 0.03)');
      grad.addColorStop(1, 'rgba(14, 165, 233, 0.04)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, width, height);
    }

    ctx.fillStyle = color;
    for (let p of particles) {
      p.x += p.speedX;
      p.y += p.speedY;

      if (p.x < 0) p.x = width;
      if (p.x > width) p.x = 0;
      if (p.y < 0) p.y = height;
      if (p.y > height) p.y = 0;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.globalAlpha = p.alpha;
      ctx.fill();
    }
    
    ctx.globalAlpha = 1.0;
    requestAnimationFrame(render);
  }
  render();
}

function initMusicPlayer() {
  const audio = document.getElementById('profile-audio');
  const toggleBtn = document.getElementById('audio-toggle-btn');
  const eq = document.getElementById('audio-eq');
  const overlay = document.getElementById('click-to-enter-overlay');
  
  if (!audio || !toggleBtn) return;

  function playAudio() {
    audio.play().then(() => {
      toggleBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';
      if (eq) eq.classList.remove('paused');
      if (overlay) overlay.style.display = 'none';
    }).catch(err => {
      console.log('Autoplay blocked. User gesture required.');
    });
  }

  function pauseAudio() {
    audio.pause();
    toggleBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
    if (eq) eq.classList.add('paused');
  }

  toggleBtn.addEventListener('click', () => {
    if (audio.paused) {
      playAudio();
    } else {
      pauseAudio();
    }
  });

  if (overlay) {
    overlay.addEventListener('click', () => {
      playAudio();
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initMusicPlayer();
});
