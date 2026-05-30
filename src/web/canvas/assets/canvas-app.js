// Canvas App - MsgStack v0.8 Fabric.js Renderer
// Global state
let canvas;
let brandSettings = {};
let designSpec = { zones: [], page_settings: { width: 850, height: 1100, grid_cols: 12, gutter: 20 } };
let activeZone = null;
let artifactId = null;
let workspaceId = null;
let customFontsLoaded = false;

// Typography config
const TYPOGRAPHY = {
  heading: { fontFamily: 'Playfair Display', fontSize: 32, fontWeight: '700', lineHeight: 1.3 },
  subhead: { fontFamily: 'Inter', fontSize: 24, fontWeight: '600', lineHeight: 1.4 },
  body: { fontFamily: 'Inter', fontSize: 16, fontWeight: '400', lineHeight: 1.6 },
  caption: { fontFamily: 'Inter', fontSize: 12, fontWeight: '400', lineHeight: 1.5 },
  tagline: { fontFamily: 'Inter', fontSize: 18, fontWeight: '500', lineHeight: 1.3 }
};

// Color palette
const COLORS = {
  primary: '#58a6ff',
  secondary: '#f0883e',
  success: '#238636',
  danger: '#da3633',
  dark: '#0f1117',
  'dark-secondary': '#161b22',
  'border': '#30363d',
  text: '#e1e4e8',
  'text-secondary': '#8b949e'
};

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
  const params = new URLSearchParams(window.location.search);
  artifactId = params.get('artifact_id');
  workspaceId = params.get('workspace_id') || 'default';

  canvas = new fabric.Canvas('fabric-canvas', {
    backgroundColor: '#ffffff',
    preserveObjectStacking: true,
    stopContextMenu: true
  });

  canvas.on('mouse:dblclick', handleDoubleClick);
  canvas.on('object:modified', handleObjectModified);
  canvas.on('object:selected', handleObjectSelected);
  canvas.on('selection:cleared', () => { activeZone = null; updateZoneList(); });

  await loadBrandSettings();
  await loadDesignSpec();
  renderAllZones();
  hideLoading();
}

function hideLoading() {
  const el = document.getElementById('loading');
  if (el) el.style.display = 'none';
}

async function loadBrandSettings() {
  try {
    const resp = await fetch(`/api/workspaces/${workspaceId}/brand`);
    if (resp.ok) {
      brandSettings = await resp.json();
      
      // Collect fonts to load dynamically
      const fontsToLoad = [];
      if (brandSettings.font_heading) {
        TYPOGRAPHY.heading.fontFamily = brandSettings.font_heading;
        fontsToLoad.push(brandSettings.font_heading);
      }
      if (brandSettings.font_body) {
        TYPOGRAPHY.subhead.fontFamily = brandSettings.font_body;
        TYPOGRAPHY.body.fontFamily = brandSettings.font_body;
        TYPOGRAPHY.caption.fontFamily = brandSettings.font_body;
        TYPOGRAPHY.tagline.fontFamily = brandSettings.font_body;
        fontsToLoad.push(brandSettings.font_body);
      }
      
      if (fontsToLoad.length > 0) {
        loadCustomFonts(fontsToLoad);
      }

      // Map DB settings fields to client-side expected variables
      brandSettings.font_primary = brandSettings.font_body || 'Inter';
      brandSettings.font_secondary = brandSettings.font_heading || 'Playfair Display';
      brandSettings.logo_url = brandSettings.logo_path || '';
    }
  } catch (e) {
    console.warn('Brand settings not available, using defaults:', e);
    brandSettings = {
      primary_color: '#58a6ff',
      secondary_color: '#f0883e',
      font_primary: 'Inter',
      font_secondary: 'Playfair Display',
      logo_url: ''
    };
  }
}

function loadCustomFonts(fonts) {
  if (customFontsLoaded) return;
  const urls = fonts.map(f => `https://fonts.googleapis.com/css2?family=${f.replace(/ /g, '+')}`).join(',');
  const link = document.createElement('link');
  link.href = urls;
  link.rel = 'stylesheet';
  document.head.appendChild(link);
  customFontsLoaded = true;
}

async function loadDesignSpec() {
  if (!artifactId) {
    designSpec = getDefaultDesignSpec();
    updateArtifactInfo();
    return;
  }
  try {
    const resp = await fetch(`/api/artifacts/${artifactId}/design_spec`);
    if (resp.ok) {
      designSpec = await resp.json();
      if (!designSpec.page_settings && designSpec.page_spec) {
        designSpec.page_settings = designSpec.page_spec;
      }
    } else {
      designSpec = getDefaultDesignSpec();
    }
  } catch (e) {
    console.warn('Could not load design spec:', e);
    designSpec = getDefaultDesignSpec();
  }
  updateArtifactInfo();
}

function getDefaultDesignSpec() {
  return {
    artifact_type: 'one_pager',
    page_settings: { width: 850, height: 1100, grid_cols: 12, gutter: 20, margin: 40 },
    zones: [
      { id: 'header', type: 'header', row: 0, col: 0, colspan: 12, height: 80, product_name: 'Product Name', badge_text: 'NEW' },
      { id: 'hero', type: 'hero', row: 1, col: 0, colspan: 12, height: 300, headline: 'Your Headline Here', bg_color: '{{brand.primary_color}}' },
      { id: 'positioning', type: 'positioning_block', row: 2, col: 0, colspan: 12, height: 100, content: 'Your positioning statement goes here. This is a 2-3 sentence paragraph that describes your product.', lead_in: 'Why choose us' },
      { id: 'pillars', type: 'pillar_grid', row: 3, col: 0, colspan: 12, height: 280, pillars: [
        { icon: '🚀', headline: 'Speed', body: 'Fast deployment and quick results.' },
        { icon: '🛡️', headline: 'Security', body: 'Enterprise-grade protection built in.' },
        { icon: '⚡', headline: 'Performance', body: 'Optimized for scale from day one.' }
      ]},
      { id: 'messages', type: 'message_list', row: 4, col: 0, colspan: 12, height: 350, messages: [
        { section_type: 'headline', content: 'Main headline message', priority: 1 },
        { section_type: 'benefit', content: 'Key benefit for users', priority: 2 },
        { section_type: 'proof_point', content: 'Customer proof point', priority: 3 }
      ]},
      { id: 'personas', type: 'persona_strip', row: 5, col: 0, colspan: 12, height: 200, personas: [
        { name: 'VP Engineering', role: 'Technical decision maker', pain_points: ['Slow deployments', 'Technical debt'] },
        { name: 'CTO', role: 'Executive sponsor', pain_points: ['Scaling issues', 'Compliance concerns'] }
      ]},
      { id: 'proof', type: 'proof_block', row: 6, col: 0, colspan: 12, height: 150, stat: '99.9%', label: 'Uptime SLA', quote: '' },
      { id: 'cta', type: 'cta_footer', row: 7, col: 0, colspan: 12, height: 120, cta_text: 'Get Started', cta_url: '#', contact_name: 'Contact Us', logo_url: '{{brand.logo_url}}' }
    ]
  };
}

function updateArtifactInfo() {
  const el = document.getElementById('artifact-info');
  if (el) el.textContent = `${designSpec.artifact_type || 'one_pager'} • ${designSpec.zones?.length || 0} zones`;
}

// Grid Layout Engine
function getRowOffsets() {
  const ps = designSpec.page_settings || designSpec.page_spec || {};
  const gutter = ps.gutter || 20;
  const margin = ps.margin || 40;
  
  let maxRow = 0;
  if (designSpec.zones) {
    designSpec.zones.forEach(z => {
      if (z.row > maxRow) maxRow = z.row;
    });
  }
  
  const rowHeights = new Array(maxRow + 1).fill(100);
  if (designSpec.zones) {
    designSpec.zones.forEach(z => {
      const r = z.row || 0;
      const h = z.height || 100;
      if (h > rowHeights[r]) {
        rowHeights[r] = h;
      }
    });
  }
  
  const offsets = new Array(maxRow + 1).fill(0);
  let currentY = margin;
  for (let i = 0; i <= maxRow; i++) {
    offsets[i] = currentY;
    currentY += rowHeights[i] + gutter;
  }
  
  return offsets;
}

function calculateZonePosition(zone) {
  const ps = designSpec.page_settings || designSpec.page_spec || {};
  const pageW = ps.width || 850;
  const cols = ps.grid_cols || 12;
  const gutter = ps.gutter || 20;
  const margin = ps.margin || 40;
  const colW = (pageW - margin * 2 - gutter * (cols - 1)) / cols;

  const x = margin + zone.col * (colW + gutter);
  const rowOffsets = getRowOffsets();
  const y = rowOffsets[zone.row || 0] || margin;
  const w = zone.colspan * colW + (zone.colspan - 1) * gutter;
  const h = zone.height || 100;

  return { x, y, w, h };
}

window._layoutChanged = false;

function renderAllZones() {
  window._layoutChanged = false;
  canvas.clear();
  const ps = designSpec.page_settings || designSpec.page_spec || {};
  canvas.setWidth(ps.width || 850);
  canvas.setHeight(ps.height || 1100);
  canvas.backgroundColor = resolveToken(ps.bg_color) || '#ffffff';

  if (!designSpec.zones) return;
  designSpec.zones.forEach(zone => renderZone(zone));
  
  if (window._layoutChanged) {
    window._layoutChanged = false;
    canvas.clear();
    designSpec.zones.forEach(zone => renderZone(zone));
  }
  
  canvas.renderAll();
  updateZoneList();
}

function normalizeZoneData(zone) {
  const norm = { ...zone };

  // 1. Header
  if (zone.type === 'header') {
    let productName = zone.product_name || 'Product Name';
    let badgeText = zone.badge_text || '';
    let logoUrl = zone.logo_url || '';
    let bgColor = zone.background || zone.bg_color || '{{brand.primary_color}}' || '#161b22';

    if (zone.text_content) {
      const parts = zone.text_content.split('|');
      productName = parts[0]?.trim() || productName;
      if (parts[1]) {
        badgeText = parts[1].trim();
      }
    }
    norm.product_name = productName;
    norm.badge_text = badgeText;
    norm.logo_url = logoUrl;
    norm.bg_color = bgColor;
  }

  // 2. Hero
  if (zone.type === 'hero') {
    let headline = zone.headline || 'Your Headline Here';
    let subhead = zone.subhead || '';
    let bgColor = zone.background || zone.bg_color || '{{brand.primary_color}}' || '#58a6ff';

    if (zone.text_content) {
      const parts = zone.text_content.split('\n');
      headline = parts[0]?.trim() || headline;
      if (parts[1]) {
        subhead = parts[1].trim();
      } else if (zone.text_content.includes('|')) {
        const p2 = zone.text_content.split('|');
        headline = p2[0].trim();
        subhead = p2[1].trim();
      }
    }
    norm.headline = headline;
    norm.subhead = subhead;
    norm.bg_color = bgColor;
  }

  // 3. Positioning Block
  if (zone.type === 'positioning_block' || zone.type === 'positioning') {
    let content = zone.content || zone.text_content || 'Positioning statement here.';
    let leadIn = zone.lead_in || '';

    if (zone.text_content && zone.text_content.includes(':')) {
      const parts = zone.text_content.split(':');
      leadIn = parts[0].trim();
      content = parts.slice(1).join(':').trim();
    }
    norm.content = content;
    norm.lead_in = leadIn;
  }

  // 4. Pillar Grid / Differentiation
  if (zone.type === 'pillar_grid' || zone.type === 'differentiation') {
    let pillars = zone.pillars || [];
    if (pillars.length === 0 && zone.list_items && zone.list_items.length > 0) {
      pillars = zone.list_items.map((item, idx) => {
        let icon = '●';
        let headline = `Pillar ${idx + 1}`;
        let body = item;

        const emojiMatch = item.match(/^([\u2700-\u27BF]|[\uE000-\uF8FF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|[\u2011-\u26FF]|\uD83E[\uDC00-\uDFFF])/g);
        if (emojiMatch) {
          icon = emojiMatch[0];
          item = item.substring(icon.length).trim();
        }

        const sepIndex = item.indexOf(':');
        const dashIndex = item.indexOf(' - ');
        if (sepIndex > -1) {
          headline = item.substring(0, sepIndex).trim();
          body = item.substring(sepIndex + 1).trim();
        } else if (dashIndex > -1) {
          headline = item.substring(0, dashIndex).trim();
          body = item.substring(dashIndex + 3).trim();
        } else if (item.length < 30) {
          headline = item;
          body = '';
        } else {
          headline = item.substring(0, 20) + '...';
          body = item;
        }

        return { icon, headline, body };
      });
    }
    norm.pillars = pillars;
  }

  // 5. Message List
  if (zone.type === 'message_list') {
    let messages = zone.messages || [];
    if (messages.length === 0 && zone.list_items && zone.list_items.length > 0) {
      messages = zone.list_items.map(item => {
        let section_type = 'benefit';
        let content = item;

        const typeMatch = item.match(/^\[(.*?)\]/);
        if (typeMatch) {
          section_type = typeMatch[1].toLowerCase();
          content = item.substring(typeMatch[0].length).trim();
        } else if (item.includes(':')) {
          const firstPart = item.split(':')[0].trim().toLowerCase();
          const validTypes = ['headline', 'subhead', 'benefit', 'proof_point', 'objection'];
          if (validTypes.includes(firstPart)) {
            section_type = firstPart;
            content = item.split(':').slice(1).join(':').trim();
          }
        }
        return { section_type, content, priority: 2 };
      });
    }
    norm.messages = messages;
  }

  // 6. Persona Strip
  if (zone.type === 'persona_strip') {
    let personas = zone.personas || [];
    if (personas.length === 0 && zone.list_items && zone.list_items.length > 0) {
      personas = zone.list_items.map((item, idx) => {
        let name = 'Persona';
        let role = 'Target Audience';
        let pain_points = [];

        if (item.includes('|')) {
          const parts = item.split('|');
          name = parts[0]?.trim() || name;
          role = parts[1]?.trim() || role;
          if (parts[2]) {
            let painStr = parts[2].trim();
            if (painStr.toLowerCase().startsWith('pain:')) {
              painStr = painStr.substring(5).trim();
            }
            pain_points = painStr.split(',').map(x => x.trim()).filter(Boolean);
          }
        } else {
          name = item;
        }

        return { name, role, pain_points };
      });
    }
    norm.personas = personas;
  }

  // 7. Proof Block
  if (zone.type === 'proof_block') {
    let stat = zone.stat || '';
    let label = zone.label || '';
    let quote = zone.quote || '';
    let bgColor = zone.background || zone.bg_color || '{{brand.primary_color}}' || '#0f1117';

    if (!stat && zone.text_content) {
      const parts = zone.text_content.includes('|') ? zone.text_content.split('|') : zone.text_content.split('\n');
      stat = parts[0]?.trim() || '';
      label = parts[1]?.trim() || '';
      quote = parts[2]?.trim() || '';
    }
    norm.stat = stat;
    norm.label = label;
    norm.quote = quote;
    norm.bg_color = bgColor;
  }

  // 8. CTA Footer
  if (zone.type === 'cta_footer') {
    let cta_text = zone.cta_text || 'Get Started';
    let cta_url = zone.cta_url || '#';
    let contact_name = zone.contact_name || '';
    let bgColor = zone.background || zone.bg_color || '{{brand.primary_color}}' || '#f6f8fa';

    if (zone.text_content) {
      const parts = zone.text_content.split('|');
      cta_text = parts[0]?.trim() || cta_text;
      contact_name = parts[1]?.trim() || contact_name;
    }
    norm.cta_text = cta_text;
    norm.cta_url = cta_url;
    norm.contact_name = contact_name;
    norm.bg_color = bgColor;
  }

  return norm;
}

function renderZone(zone) {
  const normZone = normalizeZoneData(zone);
  const { x, y, w, h } = calculateZonePosition(normZone);
  let obj;

  switch (normZone.type) {
    case 'header': obj = renderHeader(normZone, x, y, w, h); break;
    case 'hero': obj = renderHero(normZone, x, y, w, h); break;
    case 'positioning_block': obj = renderPositioningBlock(normZone, x, y, w, h); break;
    case 'pillar_grid': obj = renderPillarGrid(normZone, x, y, w, h); break;
    case 'message_list': obj = renderMessageList(normZone, x, y, w, h); break;
    case 'persona_strip': obj = renderPersonaStrip(normZone, x, y, w, h); break;
    case 'proof_block': obj = renderProofBlock(normZone, x, y, w, h); break;
    case 'cta_footer': obj = renderCtaFooter(normZone, x, y, w, h); break;
    default: obj = renderDefaultZone(normZone, x, y, w, h);
  }

  if (obj) {
    obj.data = { zoneId: normZone.id, zoneType: normZone.type };
    canvas.add(obj);
  }
}

// Zone Type Renderers
// Helper for premium drop shadows
function getPremiumShadow() {
  return new fabric.Shadow({
    color: 'rgba(15, 23, 42, 0.08)',
    blur: 16,
    offsetX: 0,
    offsetY: 6
  });
}

// Zone Type Renderers
function renderHeader(zone, x, y, w, h) {
  const group = [];
  const bgColor = resolveToken(zone.bg_color) || '#0f172a';

  const bg = new fabric.Rect({
    left: x, top: y, width: w, height: h,
    fill: bgColor, rx: 12, ry: 12,
    shadow: getPremiumShadow(),
    selectable: true, evented: true
  });
  group.push(bg);

  // Logo
  const logoUrl = resolveToken(zone.logo_url) || '';
  if (logoUrl && logoUrl !== '{{brand.logo_url}}') {
    fabric.Image.fromURL(logoUrl, img => {
      img.set({
        left: x + 24, top: y + h/2 - 18, width: 36, height: 36,
        selectable: true, evented: true,
        data: { zoneId: zone.id, type: 'logo' }
      });
      canvas.add(img);
    }, { crossOrigin: 'anonymous' });
  } else {
    const logoPlaceholder = new fabric.Rect({
      left: x + 24, top: y + h/2 - 18, width: 36, height: 36,
      fill: '#1e293b', stroke: resolveToken('{{brand.secondary_color}}') || '#3b82f6',
      strokeWidth: 1.5, rx: 8, ry: 8
    });
    const logoLabel = new fabric.Text('Logo', {
      left: x + 42, top: y + h/2, fontSize: 10,
      fontFamily: 'Outfit', fontWeight: '600', fill: '#94a3b8',
      originX: 'center', originY: 'center'
    });
    group.push(logoPlaceholder, logoLabel);
  }

  // Product name
  const productName = new fabric.Textbox(zone.product_name || 'Product Name', {
    left: x + 76, top: y + h/2, width: w - 180,
    fontSize: 20, fontWeight: '700',
    fontFamily: 'Outfit', fill: '#ffffff',
    originY: 'center'
  });
  group.push(productName);

  // Badge
  if (zone.badge_text) {
    const badgeBg = resolveToken('{{brand.secondary_color}}') || '#3b82f6';
    const badge = new fabric.Rect({
      left: x + w - 100, top: y + h/2 - 12, width: 76, height: 24,
      fill: badgeBg, rx: 12, ry: 12
    });
    const badgeText = new fabric.Textbox(zone.badge_text.toUpperCase(), {
      left: x + w - 100, top: y + h/2, width: 76, textAlign: 'center',
      fontSize: 10, fill: '#fff', fontWeight: '700', fontFamily: 'Inter',
      originY: 'center', letterSpacing: 1
    });
    group.push(badge, badgeText);
  }

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'header' };
  return g;
}

function renderHero(zone, x, y, w, h) {
  const group = [];
  const startColor = resolveToken(zone.bg_color) || resolveToken('{{brand.primary_color}}') || '#1e293b';
  const endColor = resolveToken('{{brand.secondary_color}}') || '#0f172a';

  const bg = new fabric.Rect({
    left: x, top: y, width: w, height: h,
    rx: 12, ry: 12, shadow: getPremiumShadow(),
    selectable: true
  });

  // Apply beautiful linear gradient
  const grad = new fabric.Gradient({
    type: 'linear',
    coords: { x1: 0, y1: 0, x2: w, y2: h },
    colorStops: [
      { offset: 0, color: startColor },
      { offset: 1, color: endColor }
    ]
  });
  bg.set('fill', grad);
  group.push(bg);

  if (zone.bg_image) {
    fabric.Image.fromURL(zone.bg_image, img => {
      img.set({ left: x, top: y, width: w, height: h, selectable: false, evented: false, opacity: 0.15 });
      canvas.add(img);
    }, { crossOrigin: 'anonymous' });
  }

  const headline = new fabric.Textbox(zone.headline || 'Your Headline Here', {
    left: x + 30, top: y + 40, width: w - 60,
    fontSize: 28, fontWeight: '800',
    fontFamily: 'Outfit', fill: '#ffffff',
    textAlign: 'center', lineHeight: 1.25
  });
  group.push(headline);

  let textY = y + 40 + headline.height + 20;

  if (zone.subhead) {
    const subhead = new fabric.Textbox(zone.subhead, {
      left: x + 40, top: textY, width: w - 80,
      fontSize: 16, fontWeight: '400',
      fontFamily: 'Inter', fill: 'rgba(255, 255, 255, 0.85)',
      textAlign: 'center', lineHeight: 1.5
    });
    group.push(subhead);
    textY += subhead.height + 20;
  }

  // Adjust hero zone height dynamically if needed
  const reqH = textY - y + 10;
  if (Math.abs((zone.height || 300) - reqH) > 5 && reqH > 150) {
    zone.height = reqH;
    window._layoutChanged = true;
  }

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'hero' };
  return g;
}

function renderPositioningBlock(zone, x, y, w, h) {
  const group = [];
  const bg = new fabric.Rect({
    left: x, top: y, width: w, height: h,
    fill: '#ffffff', stroke: '#e2e8f0', strokeWidth: 1.5,
    rx: 12, ry: 12, shadow: getPremiumShadow()
  });
  group.push(bg);

  let contentTop = y + 24;

  if (zone.lead_in) {
    const leadIn = new fabric.Text(zone.lead_in.toUpperCase(), {
      left: x + 24, top: y + 24, fontSize: 11, fontWeight: '700',
      fontFamily: 'Outfit', fill: resolveToken('{{brand.secondary_color}}') || '#3b82f6',
      letterSpacing: 1.5
    });
    group.push(leadIn);
    contentTop += 20;
  }

  const content = new fabric.Textbox(zone.content || 'Positioning statement here.', {
    left: x + 24, top: contentTop, width: w - 48,
    fontSize: 15, fontWeight: '400', fontFamily: 'Inter',
    fill: '#334155', lineHeight: 1.5
  });
  group.push(content);

  const minH = 100;
  const reqH = Math.max(minH, (content.top - y) + content.height + 24);
  if (Math.abs((zone.height || 100) - reqH) > 2) {
    zone.height = reqH;
    window._layoutChanged = true;
  }

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'positioning_block' };
  return g;
}

function renderPillarGrid(zone, x, y, w, h) {
  const group = [];
  const pillars = zone.pillars || [];
  if (pillars.length === 0) return renderDefaultZone(zone, x, y, w, h);
  
  const colW = w / pillars.length;
  let maxPillarH = 220;

  pillars.forEach((pillar, i) => {
    const px = x + i * colW + 10;
    const py = y + 15;
    const cardW = colW - 20;
    const cardH = h - 30;

    const card = new fabric.Rect({
      left: px, top: py, width: cardW, height: cardH,
      fill: '#ffffff', stroke: '#e2e8f0', strokeWidth: 1.5,
      rx: 12, ry: 12, shadow: getPremiumShadow()
    });
    group.push(card);

    // Decorative Icon Circle
    const iconBg = new fabric.Circle({
      left: px + cardW/2, top: py + 40, radius: 24,
      fill: '#eff6ff', originX: 'center', originY: 'center'
    });
    group.push(iconBg);

    const icon = new fabric.Text(pillar.icon || '●', {
      left: px + cardW/2, top: py + 40, fontSize: 24,
      originX: 'center', originY: 'center'
    });
    group.push(icon);

    const headline = new fabric.Textbox(pillar.headline || 'Pillar', {
      left: px + 16, top: py + 78, width: cardW - 32,
      fontSize: 15, fontWeight: '700',
      fontFamily: 'Outfit', fill: '#1e293b', textAlign: 'center'
    });
    group.push(headline);

    const body = new fabric.Textbox(pillar.body || '', {
      left: px + 16, top: py + 114, width: cardW - 32,
      fontSize: 13, fontFamily: 'Inter', fill: '#475569',
      lineHeight: 1.45, textAlign: 'center'
    });
    group.push(body);
    
    const reqH = (body.top - y) + body.height + 25;
    if (reqH > maxPillarH) {
      maxPillarH = reqH;
    }
  });

  if (Math.abs((zone.height || 100) - maxPillarH) > 2) {
    zone.height = maxPillarH;
    window._layoutChanged = true;
  }

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'pillar_grid' };
  return g;
}

function renderMessageList(zone, x, y, w, h) {
  const group = [];
  const messages = zone.messages || [];
  const labelColors = {
    headline: { text: '#2563eb', bg: '#eff6ff' },
    subhead: { text: '#d97706', bg: '#fef3c7' },
    benefit: { text: '#059669', bg: '#ecfdf5' },
    proof_point: { text: '#dc2626', bg: '#fef2f2' },
    objection: { text: '#4b5563', bg: '#f3f4f6' }
  };

  const bg = new fabric.Rect({
    left: x, top: y, width: w, height: h,
    fill: '#f8fafc', stroke: '#e2e8f0', strokeWidth: 1.5,
    rx: 12, ry: 12, shadow: getPremiumShadow()
  });
  group.push(bg);

  let currentItemY = y + 20;

  messages.forEach((msg, i) => {
    const labelStyle = labelColors[msg.section_type] || { text: '#2563eb', bg: '#eff6ff' };

    // Tag badge rect
    const badgeWidth = 80;
    const badgeHeight = 18;
    const badge = new fabric.Rect({
      left: x + 24, top: currentItemY, width: badgeWidth, height: badgeHeight,
      fill: labelStyle.bg, rx: 6, ry: 6
    });
    group.push(badge);

    const labelText = new fabric.Textbox((msg.section_type || 'message').toUpperCase(), {
      left: x + 24, top: currentItemY + badgeHeight / 2, width: badgeWidth,
      textAlign: 'center', fontSize: 9, fontWeight: '700',
      fontFamily: 'Outfit', fill: labelStyle.text, originY: 'center', letterSpacing: 0.5
    });
    group.push(labelText);

    const content = new fabric.Textbox(msg.content || '', {
      left: x + 24, top: currentItemY + 24, width: w - 48, fontSize: 13.5,
      fontFamily: 'Inter', fill: '#334155', lineHeight: 1.4
    });
    group.push(content);

    currentItemY += 24 + content.height + 20;

    if (i < messages.length - 1) {
      const line = new fabric.Line([x + 24, currentItemY - 10, x + w - 24, currentItemY - 10], {
        stroke: '#e2e8f0', strokeWidth: 1.2
      });
      group.push(line);
    }
  });

  const minH = 120;
  const reqH = Math.max(minH, currentItemY - y + 10);
  if (Math.abs((zone.height || 100) - reqH) > 2) {
    zone.height = reqH;
    window._layoutChanged = true;
  }

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'message_list' };
  return g;
}

function renderPersonaStrip(zone, x, y, w, h) {
  const group = [];
  const personas = zone.personas || [];
  if (personas.length === 0) return renderDefaultZone(zone, x, y, w, h);

  const cardW = Math.min(220, (w - 40) / personas.length - 20);
  let maxStripH = 180;

  const bg = new fabric.Rect({
    left: x, top: y, width: w, height: h,
    fill: '#f8fafc', stroke: '#e2e8f0', strokeWidth: 1.5,
    rx: 12, ry: 12, shadow: getPremiumShadow()
  });
  group.push(bg);

  personas.forEach((p, i) => {
    const px = x + 20 + i * (cardW + 20);
    const py = y + 20;
    const cardH = h - 40;

    const card = new fabric.Rect({
      left: px, top: py, width: cardW, height: cardH,
      fill: '#ffffff', stroke: '#e2e8f0', strokeWidth: 1.5,
      rx: 12, ry: 12, shadow: getPremiumShadow()
    });
    group.push(card);

    // Decorative colored top bar on card
    const topBar = new fabric.Rect({
      left: px, top: py, width: cardW, height: 6,
      fill: resolveToken('{{brand.primary_color}}') || '#3b82f6',
      rx: 6, ry: 6
    });
    group.push(topBar);

    const name = new fabric.Textbox(p.name || 'Persona', {
      left: px + 16, top: py + 16, width: cardW - 32,
      fontSize: 14, fontWeight: '700',
      fontFamily: 'Outfit', fill: '#1e293b'
    });
    group.push(name);

    const role = new fabric.Textbox(p.role || 'Role', {
      left: px + 16, top: py + 36, width: cardW - 32,
      fontSize: 11, fontWeight: '500', fontFamily: 'Inter',
      fill: resolveToken('{{brand.secondary_color}}') || '#3b82f6'
    });
    group.push(role);

    let painY = py + 56;
    if (p.pain_points && p.pain_points.length > 0) {
      p.pain_points.slice(0, 3).forEach((pp) => {
        const pain = new fabric.Textbox(`• ${pp}`, {
          left: px + 16, top: painY, width: cardW - 32, fontSize: 10.5,
          fontFamily: 'Inter', fill: '#475569', lineHeight: 1.3
        });
        group.push(pain);
        painY += pain.height + 8;
      });
    }

    const reqH = painY - y + 25;
    if (reqH > maxStripH) {
      maxStripH = reqH;
    }
  });

  if (Math.abs((zone.height || 100) - maxStripH) > 2) {
    zone.height = maxStripH;
    window._layoutChanged = true;
  }

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'persona_strip' };
  return g;
}

function renderProofBlock(zone, x, y, w, h) {
  const group = [];
  const startColor = resolveToken(zone.bg_color) || '#0f172a';

  const bg = new fabric.Rect({
    left: x, top: y, width: w, height: h,
    rx: 12, ry: 12, shadow: getPremiumShadow()
  });

  // Dark slate linear gradient
  const grad = new fabric.Gradient({
    type: 'linear',
    coords: { x1: 0, y1: 0, x2: w, y2: h },
    colorStops: [
      { offset: 0, color: startColor },
      { offset: 1, color: '#1e293b' }
    ]
  });
  bg.set('fill', grad);
  group.push(bg);

  let blockY = y + 24;

  if (zone.stat) {
    const statColor = resolveToken('{{brand.secondary_color}}') || '#3b82f6';
    const stat = new fabric.Textbox(zone.stat, {
      left: x + 24, top: blockY, width: w - 48, fontSize: 52, fontWeight: '900',
      fontFamily: 'Outfit', fill: statColor, textAlign: 'center'
    });
    group.push(stat);
    blockY += stat.height + 8;
  }

  if (zone.label) {
    const label = new fabric.Textbox(zone.label.toUpperCase(), {
      left: x + 24, top: blockY, width: w - 48, fontSize: 11, fontWeight: '700',
      fontFamily: 'Inter', fill: '#94a3b8', textAlign: 'center', letterSpacing: 1.5
    });
    group.push(label);
    blockY += label.height + 16;
  }

  if (zone.quote) {
    const quote = new fabric.Textbox(`“${zone.quote}”`, {
      left: x + 40, top: blockY, width: w - 80, fontSize: 13,
      fontFamily: 'Lora', fill: 'rgba(255, 255, 255, 0.85)',
      fontStyle: 'italic', textAlign: 'center', lineHeight: 1.55
    });
    group.push(quote);
    blockY += quote.height + 24;
  } else {
    blockY += 10;
  }

  const minH = 120;
  const reqH = Math.max(minH, blockY - y);
  if (Math.abs((zone.height || 100) - reqH) > 2) {
    zone.height = reqH;
    window._layoutChanged = true;
  }

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'proof_block' };
  return g;
}

function renderCtaFooter(zone, x, y, w, h) {
  const group = [];
  const bg = new fabric.Rect({
    left: x, top: y, width: w, height: h,
    fill: '#f8fafc', stroke: '#e2e8f0', strokeWidth: 1.5,
    rx: 12, ry: 12, shadow: getPremiumShadow()
  });
  group.push(bg);

  const btnBg = resolveToken('{{brand.primary_color}}') || '#0f172a';
  const ctaBtn = new fabric.Rect({
    left: x + w/2 - 100, top: y + 24, width: 200, height: 40,
    fill: btnBg, rx: 20, ry: 20, shadow: getPremiumShadow()
  });
  group.push(ctaBtn);

  const ctaText = new fabric.Textbox(zone.cta_text || 'Learn More', {
    left: x + w/2 - 80, top: y + 44, width: 160, fontSize: 14, fontWeight: '700',
    fontFamily: 'Outfit', fill: '#ffffff', originY: 'center', textAlign: 'center', letterSpacing: 0.5
  });
  group.push(ctaText);

  let contactY = y + 80;
  if (zone.contact_name) {
    const contact = new fabric.Textbox(zone.contact_name, {
      left: x + 24, top: contactY, width: w - 48, fontSize: 11, fontFamily: 'Inter',
      fill: '#64748b', textAlign: 'center'
    });
    group.push(contact);
    contactY += contact.height + 15;
  }

  // Logo upload/rendering in footer
  const logoUrl = resolveToken(zone.logo_url) || '';
  if (logoUrl && logoUrl !== '{{brand.logo_url}}') {
    fabric.Image.fromURL(logoUrl, img => {
      img.set({ left: x + 24, top: y + h/2 - 15, width: 30, height: 30, selectable: true });
      canvas.add(img);
    });
  }

  const reqH = Math.max(110, contactY - y);
  if (Math.abs((zone.height || 120) - reqH) > 2) {
    zone.height = reqH;
    window._layoutChanged = true;
  }

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'cta_footer' };
  return g;
}

function renderDefaultZone(zone, x, y, w, h) {
  const rect = new fabric.Rect({
    left: x, top: y, width: w, height: h, fill: 'rgba(59, 130, 246, 0.08)',
    stroke: '#3b82f6', strokeWidth: 2, rx: 8, ry: 8, selectable: true, evented: true
  });
  const label = new fabric.Text(zone.type || 'unknown', {
    left: x + 12, top: y + 12, fontSize: 12, fill: '#3b82f6', fontWeight: '700', fontFamily: 'Outfit'
  });
  const g = new fabric.Group([rect, label], { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: zone.type };
  return g;
}


// Brand Token Resolution
function resolveToken(value) {
  if (!value || typeof value !== 'string') return value;
  if (!value.includes('{{brand.')) return value;

  return value.replace(/\{\{brand\.(\w+)\}\}/g, (match, token) => {
    const tokenMap = {
      primary_color: brandSettings.primary_color || '#58a6ff',
      secondary_color: brandSettings.secondary_color || '#f0883e',
      text_color: brandSettings.text_color || '#1f2328',
      bg_color: brandSettings.bg_color || '#ffffff',
      font_primary: brandSettings.font_body || brandSettings.font_primary || 'Inter',
      font_secondary: brandSettings.font_heading || brandSettings.font_secondary || 'Playfair Display',
      logo_url: brandSettings.logo_path || brandSettings.logo_url || ''
    };
    return tokenMap[token] || match;
  });
}

// Typography Rendering
function createTextObject(text, style, options = {}) {
  const config = { ...TYPOGRAPHY[style] || TYPOGRAPHY.body, ...options };
  return new fabric.Text(text, {
    fontFamily: config.fontFamily,
    fontSize: config.fontSize,
    fontWeight: config.fontWeight,
    lineHeight: config.lineHeight,
    fill: config.fill || '#1f2328',
    ...options
  });
}

// Interactive Editing
function handleDoubleClick(e) {
  if (!e.target || !e.target.data) return;
  const zoneId = e.target.data.zoneId;
  const zone = designSpec.zones.find(z => z.id === zoneId);
  if (!zone) return;

  activeZone = zone;
  openEditPanel(zone);
}

function handleObjectModified(e) {
  if (!e.target || !e.target.data) return;
  const zoneId = e.target.data.zoneId;
  const zone = designSpec.zones.find(z => z.id === zoneId);
  if (!zone) return;

  const obj = e.target;
  const rowOffsets = getRowOffsets();
  let bestRow = 0;
  let minDiff = Infinity;
  for (let r = 0; r < rowOffsets.length; r++) {
    const diff = Math.abs(rowOffsets[r] - obj.top);
    if (diff < minDiff) {
      minDiff = diff;
      bestRow = r;
    }
  }

  const ps = designSpec.page_settings || designSpec.page_spec || {};
  const gutter = ps.gutter || 20;
  const lastRowY = rowOffsets[rowOffsets.length - 1] + (zone.height || 100) + gutter;
  if (obj.top > lastRowY - gutter) {
    bestRow = rowOffsets.length;
  }

  if (bestRow !== zone.row) {
    zone.row = bestRow;
    renderAllZones();
    saveDesignSpec();
  }
}

function handleObjectSelected(e) {
  if (!e.target || !e.target.data) return;
  const zoneId = e.target.data.zoneId;
  activeZone = designSpec.zones.find(z => z.id === zoneId);
  updateZoneList();
}

function updateZoneList() {
  const container = document.getElementById('zone-list');
  if (!container) return;

  container.innerHTML = designSpec.zones?.map(z => `
    <div class="zone-item ${activeZone?.id === z.id ? 'active' : ''}" onclick="selectZone('${z.id}')">
      <span class="zone-type">${z.type}</span>
      <span class="zone-name">${z.id}</span>
    </div>
  `).join('') || '';
}

function selectZone(zoneId) {
  activeZone = designSpec.zones.find(z => z.id === zoneId);
  const obj = canvas.getObjects().find(o => o.data?.zoneId === zoneId);
  if (obj) canvas.setActiveObject(obj);
  updateZoneList();
  openEditPanel(activeZone);
}

function openEditPanel(zone) {
  if (!zone) return;
  const panel = document.getElementById('edit-panel');
  const form = document.getElementById('edit-form');
  if (!panel || !form) return;

  const normalized = normalizeZoneData(zone);
  let html = `<div class="form-group"><label>Zone Type</label><input disabled value="${normalized.type}"></div>`;

  switch (normalized.type) {
    case 'header':
      html += `
        <div class="form-group"><label>Product Name</label><input id="edit-product-name" value="${normalized.product_name || ''}"></div>
        <div class="form-group"><label>Badge Text</label><input id="edit-badge" value="${normalized.badge_text || ''}"></div>
        <div class="form-group"><label>Background Color</label><div class="color-input"><input type="color" id="edit-header-bg" value="${resolveToken(normalized.bg_color) || '#161b22'}"><input id="edit-header-bg-text" value="${normalized.bg_color || ''}"></div></div>
      `;
      break;
    case 'hero':
      html += `
        <div class="form-group"><label>Headline</label><textarea id="edit-headline">${normalized.headline || ''}</textarea></div>
        <div class="form-group"><label>Subhead</label><input id="edit-subhead" value="${normalized.subhead || ''}"></div>
        <div class="form-group"><label>Background Color</label><div class="color-input"><input type="color" id="edit-hero-bg" value="${resolveToken(normalized.bg_color) || '#58a6ff'}"><input id="edit-hero-bg-text" value="${normalized.bg_color || ''}"></div></div>
        <div class="form-group"><label>Background Image URL</label><input id="edit-hero-bg-image" value="${normalized.bg_image || ''}"></div>
      `;
      break;
    case 'positioning_block':
    case 'positioning':
      html += `
        <div class="form-group"><label>Lead-in Label</label><input id="edit-lead-in" value="${normalized.lead_in || ''}"></div>
        <div class="form-group"><label>Content</label><textarea id="edit-content">${normalized.content || ''}</textarea></div>
      `;
      break;
    case 'pillar_grid':
    case 'differentiation':
      html += `<div id="edit-pillars">`;
      (normalized.pillars || []).forEach((p, i) => {
        html += `
          <div style="border:1px solid #30363d;padding:8px;margin:4px 0;border-radius:4px">
            <div class="form-group"><label>Pillar ${i+1} Icon</label><input id="edit-pillar-icon-${i}" value="${p.icon || ''}"></div>
            <div class="form-group"><label>Headline</label><input id="edit-pillar-headline-${i}" value="${p.headline || ''}"></div>
            <div class="form-group"><label>Body</label><textarea id="edit-pillar-body-${i}">${p.body || ''}</textarea></div>
          </div>
        `;
      });
      html += `</div>`;
      break;
    case 'message_list':
      html += `<div id="edit-messages">`;
      (normalized.messages || []).forEach((m, i) => {
        html += `
          <div style="border:1px solid #30363d;padding:8px;margin:4px 0;border-radius:4px">
            <div class="form-group"><label>Section Type</label>
              <select id="edit-msg-type-${i}">
                <option ${m.section_type === 'headline' ? 'selected' : ''}>headline</option>
                <option ${m.section_type === 'subhead' ? 'selected' : ''}>subhead</option>
                <option ${m.section_type === 'benefit' ? 'selected' : ''}>benefit</option>
                <option ${m.section_type === 'proof_point' ? 'selected' : ''}>proof_point</option>
                <option ${m.section_type === 'objection' ? 'selected' : ''}>objection</option>
              </select>
            </div>
            <div class="form-group"><label>Content</label><textarea id="edit-msg-content-${i}">${m.content || ''}</textarea></div>
          </div>
        `;
      });
      html += `</div>`;
      break;
    case 'persona_strip':
      html += `<div id="edit-personas">`;
      (normalized.personas || []).forEach((p, i) => {
        html += `
          <div style="border:1px solid #30363d;padding:8px;margin:4px 0;border-radius:4px">
            <div class="form-group"><label>Persona ${i+1} Name</label><input id="edit-persona-name-${i}" value="${p.name || ''}"></div>
            <div class="form-group"><label>Role</label><input id="edit-persona-role-${i}" value="${p.role || ''}"></div>
            <div class="form-group"><label>Pain Points (comma-separated)</label><textarea id="edit-persona-pain-${i}">${(p.pain_points || []).join(', ')}</textarea></div>
          </div>
        `;
      });
      html += `</div>`;
      break;
    case 'cta_footer':
      html += `
        <div class="form-group"><label>CTA Text</label><input id="edit-cta-text" value="${normalized.cta_text || ''}"></div>
        <div class="form-group"><label>CTA URL</label><input id="edit-cta-url" value="${normalized.cta_url || ''}"></div>
        <div class="form-group"><label>Contact Info</label><input id="edit-contact" value="${normalized.contact_name || ''}"></div>
        <div class="form-group"><label>Background Color</label><div class="color-input"><input type="color" id="edit-cta-bg" value="${resolveToken(normalized.bg_color) || '#f6f8fa'}"><input id="edit-cta-bg-text" value="${normalized.bg_color || ''}"></div></div>
      `;
      break;
    case 'proof_block':
      html += `
        <div class="form-group"><label>Stat (large number)</label><input id="edit-stat" value="${normalized.stat || ''}"></div>
        <div class="form-group"><label>Label</label><input id="edit-label" value="${normalized.label || ''}"></div>
        <div class="form-group"><label>Quote</label><textarea id="edit-quote">${normalized.quote || ''}</textarea></div>
        <div class="form-group"><label>Background Color</label><div class="color-input"><input type="color" id="edit-proof-bg" value="${resolveToken(normalized.bg_color) || '#0f1117'}"><input id="edit-proof-bg-text" value="${normalized.bg_color || ''}"></div></div>
      `;
      break;
  }

  form.innerHTML = html;
  panel.classList.add('open');
}

function saveZoneEdit() {
  if (!activeZone) return;

  const type = activeZone.type;

  switch (type) {
    case 'header': {
      const prodName = document.getElementById('edit-product-name')?.value || '';
      const badgeText = document.getElementById('edit-badge')?.value || '';
      activeZone.product_name = prodName;
      activeZone.badge_text = badgeText;
      activeZone.bg_color = document.getElementById('edit-header-bg-text')?.value || activeZone.bg_color;
      activeZone.background = activeZone.bg_color;
      activeZone.text_content = badgeText ? `${prodName} | ${badgeText}` : prodName;
      break;
    }
    case 'hero': {
      const headline = document.getElementById('edit-headline')?.value || '';
      const subhead = document.getElementById('edit-subhead')?.value || '';
      activeZone.headline = headline;
      activeZone.subhead = subhead;
      activeZone.bg_color = document.getElementById('edit-hero-bg-text')?.value || activeZone.bg_color;
      activeZone.background = activeZone.bg_color;
      activeZone.bg_image = document.getElementById('edit-hero-bg-image')?.value || activeZone.bg_image;
      activeZone.text_content = subhead ? `${headline}\n${subhead}` : headline;
      break;
    }
    case 'positioning_block':
    case 'positioning': {
      const leadIn = document.getElementById('edit-lead-in')?.value || '';
      const content = document.getElementById('edit-content')?.value || '';
      activeZone.lead_in = leadIn;
      activeZone.content = content;
      activeZone.text_content = leadIn ? `${leadIn}: ${content}` : content;
      break;
    }
    case 'pillar_grid':
    case 'differentiation': {
      const pillars = (activeZone.pillars || []).map((p, i) => ({
        icon: document.getElementById(`edit-pillar-icon-${i}`)?.value || p.icon,
        headline: document.getElementById(`edit-pillar-headline-${i}`)?.value || p.headline,
        body: document.getElementById(`edit-pillar-body-${i}`)?.value || p.body
      }));
      activeZone.pillars = pillars;
      activeZone.list_items = pillars.map(p => `${p.icon} ${p.headline}: ${p.body}`);
      break;
    }
    case 'message_list': {
      const messages = (activeZone.messages || []).map((m, i) => ({
        section_type: document.getElementById(`edit-msg-type-${i}`)?.value || m.section_type,
        content: document.getElementById(`edit-msg-content-${i}`)?.value || m.content
      }));
      activeZone.messages = messages;
      activeZone.list_items = messages.map(m => `[${m.section_type}] ${m.content}`);
      break;
    }
    case 'persona_strip': {
      const numPersonas = activeZone.personas ? activeZone.personas.length : (activeZone.list_items ? activeZone.list_items.length : 0);
      const personas = [];
      for (let i = 0; i < numPersonas; i++) {
        const name = document.getElementById(`edit-persona-name-${i}`)?.value || '';
        const role = document.getElementById(`edit-persona-role-${i}`)?.value || '';
        const painStr = document.getElementById(`edit-persona-pain-${i}`)?.value || '';
        const pain_points = painStr.split(',').map(x => x.trim()).filter(Boolean);
        personas.push({ name, role, pain_points });
      }
      activeZone.personas = personas;
      activeZone.list_items = personas.map(p => `${p.name} | ${p.role} | Pain: ${p.pain_points.join(', ')}`);
      break;
    }
    case 'cta_footer': {
      const ctaText = document.getElementById('edit-cta-text')?.value || '';
      const contact = document.getElementById('edit-contact')?.value || '';
      activeZone.cta_text = ctaText;
      activeZone.cta_url = document.getElementById('edit-cta-url')?.value || activeZone.cta_url;
      activeZone.contact_name = contact;
      activeZone.bg_color = document.getElementById('edit-cta-bg-text')?.value || activeZone.bg_color;
      activeZone.background = activeZone.bg_color;
      activeZone.text_content = contact ? `${ctaText} | ${contact}` : ctaText;
      break;
    }
    case 'proof_block': {
      const stat = document.getElementById('edit-stat')?.value || '';
      const label = document.getElementById('edit-label')?.value || '';
      const quote = document.getElementById('edit-quote')?.value || '';
      activeZone.stat = stat;
      activeZone.label = label;
      activeZone.quote = quote;
      activeZone.bg_color = document.getElementById('edit-proof-bg-text')?.value || activeZone.bg_color;
      activeZone.background = activeZone.bg_color;
      activeZone.text_content = quote ? `${stat} | ${label} | ${quote}` : `${stat} | ${label}`;
      break;
    }
  }

  renderAllZones();
  saveDesignSpec();
  showToast('Zone updated');
}

function deleteZone() {
  if (!activeZone) return;
  if (!confirm('Delete this zone?')) return;
  designSpec.zones = designSpec.zones.filter(z => z.id !== activeZone.id);
  activeZone = null;
  closeEditPanel();
  renderAllZones();
  saveDesignSpec();
}

function closeEditPanel() {
  document.getElementById('edit-panel')?.classList.remove('open');
}

// Logo drag-and-drop
canvas.on('drop:data', function(e) {
  const data = e.e.dataTransfer?.getData('text/plain');
  if (data && activeZone) {
    if (activeZone.type === 'header' || activeZone.type === 'cta_footer') {
      activeZone.logo_url = data;
      renderAllZones();
      saveDesignSpec();
    }
  }
});

// Export Functions
function exportPNG() {
  const dataURL = canvas.toDataURL({ format: 'png', multiplier: 2.0, quality: 1.0 });
  downloadFile(dataURL, `artifact-${artifactId || 'export'}.png`);
  showToast('PNG exported');
}

function exportPDF() {
  try {
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ orientation: 'portrait', unit: 'px', format: [designSpec.page_settings?.width || 850, designSpec.page_settings?.height || 1100] });
    const dataURL = canvas.toDataURL({ format: 'jpeg', multiplier: 2.0, quality: 0.95 });
    pdf.addImage(dataURL, 'JPEG', 0, 0, pdf.internal.pageSize.getWidth(), pdf.internal.pageSize.getHeight());
    pdf.save(`artifact-${artifactId || 'export'}.pdf`);
    showToast('PDF exported');
  } catch (e) {
    showToast('PDF export failed - jsPDF not loaded', true);
  }
}

function exportSVG() {
  const svg = canvas.toSVG();
  const blob = new Blob([svg], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  downloadFile(url, `artifact-${artifactId || 'export'}.svg`);
  showToast('SVG exported');
}

function exportPrint() {
  const origMultiplier = 2.0;
  const printMultiplier = 300 / 72; // 300 DPI equivalent
  const dataURL = canvas.toDataURL({ format: 'png', multiplier: printMultiplier, quality: 1.0 });
  downloadFile(dataURL, `artifact-${artifactId || 'export'}-print-300dpi.png`);
  showToast('Print-ready PNG exported (300 DPI)');
}

function downloadFile(url, filename) {
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  if (url.startsWith('blob:')) URL.revokeObjectURL(url);
}

// Save design spec
async function saveDesignSpec() {
  if (!artifactId) return;
  if (!designSpec.page_spec && designSpec.page_settings) {
    designSpec.page_spec = designSpec.page_settings;
  }
  try {
    await fetch(`/api/artifacts/${artifactId}/design_spec`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(designSpec)
    });
  } catch (e) {
    console.warn('Failed to save design spec:', e);
  }
}

async function resetToAI() {
  if (!confirm('Reset all changes and reload AI version?')) return;
  try {
    await fetch(`/api/artifacts/${artifactId}/design_spec/reset`, { method: 'POST' });
    await loadDesignSpec();
    renderAllZones();
    showToast('Reset to AI version');
  } catch (e) {
    designSpec = getDefaultDesignSpec();
    renderAllZones();
    showToast('Reset to default (server unavailable)');
  }
}

function showToast(msg, isError = false) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.style.background = isError ? '#da3633' : '#238636';
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
}

// Image upload handler
function handleLogoUpload(input) {
  if (!input.files || !input.files[0]) return;
  const reader = new FileReader();
  reader.onload = function(e) {
    const base64 = e.target.result;
    if (activeZone) {
      activeZone.logo_url = base64;
      renderAllZones();
      saveDesignSpec();
    }
  };
  reader.readAsDataURL(input.files[0]);
}

// Make functions available globally
window.exportPNG = exportPNG;
window.exportPDF = exportPDF;
window.exportSVG = exportSVG;
window.exportPrint = exportPrint;
window.resetToAI = resetToAI;
window.saveZoneEdit = saveZoneEdit;
window.closeEditPanel = closeEditPanel;
window.deleteZone = deleteZone;
window.selectZone = selectZone;
window.handleLogoUpload = handleLogoUpload;
