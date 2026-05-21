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
      if (brandSettings.custom_fonts) loadCustomFonts(brandSettings.custom_fonts);
      // Update typography config with brand fonts
      if (brandSettings.font_heading) TYPOGRAPHY.heading.fontFamily = brandSettings.font_heading;
      if (brandSettings.font_body) {
        TYPOGRAPHY.subhead.fontFamily = brandSettings.font_body;
        TYPOGRAPHY.body.fontFamily = brandSettings.font_body;
        TYPOGRAPHY.caption.fontFamily = brandSettings.font_body;
        TYPOGRAPHY.tagline.fontFamily = brandSettings.font_body;
      }
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

function renderAllZones() {
  canvas.clear();
  const ps = designSpec.page_settings || designSpec.page_spec || {};
  canvas.setWidth(ps.width || 850);
  canvas.setHeight(ps.height || 1100);
  canvas.backgroundColor = resolveToken(ps.bg_color) || '#ffffff';

  if (!designSpec.zones) return;
  designSpec.zones.forEach(zone => renderZone(zone));
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
function renderHeader(zone, x, y, w, h) {
  const group = [];
  const bgColor = resolveToken(zone.bg_color) || '#161b22';

  const bg = new fabric.Rect({ left: x, top: y, width: w, height: h, fill: bgColor, selectable: true, evented: true });
  group.push(bg);

  // Logo
  const logoUrl = resolveToken(zone.logo_url) || '';
  if (logoUrl && logoUrl !== '{{brand.logo_url}}') {
    fabric.Image.fromURL(logoUrl, img => {
      img.set({ left: x + 20, top: y + h/2 - 20, width: 40, height: 40, selectable: true, evented: true, data: { zoneId: zone.id, type: 'logo' } });
      canvas.add(img);
    }, { crossOrigin: 'anonymous' });
  } else {
    const logoPlaceholder = new fabric.Rect({ left: x + 20, top: y + h/2 - 20, width: 40, height: 40, fill: '#30363d', stroke: '#58a6ff', strokeWidth: 1, rx: 4 });
    const logoLabel = new fabric.Text('Logo', { left: x + 40, top: y + h/2, fontSize: 10, fill: '#8b949e', originX: 'center', originY: 'center' });
    group.push(logoPlaceholder, logoLabel);
  }

  // Product name
  const productName = new fabric.Text(zone.product_name || 'Product Name', {
    left: x + 80, top: y + h/2, fontSize: 20, fontWeight: '700',
    fontFamily: brandSettings.font_primary || 'Inter', fill: resolveToken('{{brand.text_color}}') || '#e1e4e8',
    originY: 'center'
  });
  group.push(productName);

  // Badge
  if (zone.badge_text) {
    const badge = new fabric.Rect({ left: x + w - 80, top: y + h/2 - 14, width: 60, height: 28, fill: '#238636', rx: 14 });
    const badgeText = new fabric.Text(zone.badge_text, { left: x + w - 50, top: y + h/2, fontSize: 12, fill: '#fff', fontWeight: '600', originX: 'center', originY: 'center' });
    group.push(badge, badgeText);
  }

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'header' };
  return g;
}

function renderHero(zone, x, y, w, h) {
  const group = [];
  const bgColor = resolveToken(zone.bg_color) || resolveToken('{{brand.primary_color}}') || '#58a6ff';

  const bg = new fabric.Rect({ left: x, top: y, width: w, height: h, fill: bgColor, selectable: true });
  group.push(bg);

  if (zone.bg_image) {
    fabric.Image.fromURL(zone.bg_image, img => {
      img.set({ left: x, top: y, width: w, height: h, selectable: false, evented: false, opacity: 0.3 });
      canvas.add(img);
    }, { crossOrigin: 'anonymous' });
  }

  const headline = new fabric.Textbox(zone.headline || 'Your Headline Here', {
    left: x + 20, top: y + h/2 - 60, width: w - 40, fontSize: 32, fontWeight: '800',
    fontFamily: brandSettings.font_secondary || 'Playfair Display',
    fill: '#ffffff', textAlign: 'center'
  });
  group.push(headline);

  if (zone.subhead) {
    const subhead = new fabric.Textbox(zone.subhead, {
      left: x + 30, top: y + h/2 + 20, width: w - 60, fontSize: 18, fontWeight: '400',
      fontFamily: brandSettings.font_primary || 'Inter', fill: 'rgba(255,255,255,0.9)',
      textAlign: 'center'
    });
    group.push(subhead);
  }

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'hero' };
  return g;
}

function renderPositioningBlock(zone, x, y, w, h) {
  const group = [];
  const bg = new fabric.Rect({ left: x, top: y, width: w, height: h, fill: '#f6f8fa', stroke: '#d0d7de', strokeWidth: 1, rx: 8 });
  group.push(bg);

  if (zone.lead_in) {
    const leadIn = new fabric.Text(zone.lead_in.toUpperCase(), {
      left: x + 20, top: y + 20, fontSize: 11, fontWeight: '600',
      fontFamily: 'Inter', fill: resolveToken('{{brand.primary_color}}') || '#58a6ff',
      letterSpacing: 2
    });
    group.push(leadIn);
  }

  const content = new fabric.Textbox(zone.content || 'Positioning statement here.', {
    left: x + 20, top: y + (zone.lead_in ? 45 : 20), width: w - 40,
    fontSize: 16, fontWeight: '400', fontFamily: 'Inter',
    fill: '#1f2328', lineHeight: 1.4
  });
  group.push(content);

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'positioning_block' };
  return g;
}

function renderPillarGrid(zone, x, y, w, h) {
  const group = [];
  const pillars = zone.pillars || [];
  const colW = w / pillars.length;

  pillars.forEach((pillar, i) => {
    const px = x + i * colW + 10;
    const py = y + 20;
    const cardW = colW - 20;
    const cardH = h - 40;

    const card = new fabric.Rect({ left: px, top: py, width: cardW, height: cardH, fill: '#ffffff', stroke: '#d0d7de', strokeWidth: 1, rx: 8 });
    group.push(card);

    const icon = new fabric.Text(pillar.icon || '●', {
      left: px + cardW/2, top: py + 30, fontSize: 36, originX: 'center', originY: 'center'
    });
    group.push(icon);

    const headline = new fabric.Textbox(pillar.headline || 'Pillar', {
      left: px + 10, top: py + 75, width: cardW - 20, fontSize: 16, fontWeight: '700',
      fontFamily: 'Inter', fill: '#1f2328', textAlign: 'center'
    });
    group.push(headline);

    const body = new fabric.Textbox(pillar.body || '', {
      left: px + 15, top: py + 110, width: cardW - 30, fontSize: 13,
      fontFamily: 'Inter', fill: '#656d76', lineHeight: 1.4, textAlign: 'left'
    });
    group.push(body);
  });

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'pillar_grid' };
  return g;
}

function renderMessageList(zone, x, y, w, h) {
  const group = [];
  const messages = zone.messages || [];
  const sectionColors = { headline: '#58a6ff', subhead: '#f0883e', benefit: '#238636', proof_point: '#da3633', objection: '#8b949e' };

  const bg = new fabric.Rect({ left: x, top: y, width: w, height: h, fill: '#f6f8fa', rx: 8 });
  group.push(bg);

  messages.forEach((msg, i) => {
    const my = y + 20 + i * 85;
    const color = sectionColors[msg.section_type] || '#58a6ff';

    const label = new fabric.Text((msg.section_type || 'message').toUpperCase(), {
      left: x + 20, top: my, fontSize: 10, fontWeight: '700',
      fontFamily: 'Inter', fill: color, letterSpacing: 1.5
    });
    group.push(label);

    const content = new fabric.Textbox(msg.content || '', {
      left: x + 20, top: my + 18, width: w - 40, fontSize: 13,
      fontFamily: 'Inter', fill: '#1f2328', lineHeight: 1.3
    });
    group.push(content);

    if (i < messages.length - 1) {
      const line = new fabric.Line([x + 20, my + 75, x + w - 20, my + 75], { stroke: '#d0d7de', strokeWidth: 1 });
      group.push(line);
    }
  });

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'message_list' };
  return g;
}

function renderPersonaStrip(zone, x, y, w, h) {
  const group = [];
  const personas = zone.personas || [];
  const cardW = Math.min(200, (w - 40) / personas.length - 20);

  const bg = new fabric.Rect({ left: x, top: y, width: w, height: h, fill: '#f6f8fa', rx: 8 });
  group.push(bg);

  personas.forEach((p, i) => {
    const px = x + 20 + i * (cardW + 20);
    const py = y + 20;
    const cardH = h - 40;

    const card = new fabric.Rect({ left: px, top: py, width: cardW, height: cardH, fill: '#ffffff', stroke: '#d0d7de', strokeWidth: 1, rx: 8 });
    group.push(card);

    const name = new fabric.Textbox(p.name || 'Persona', {
      left: px + 15, top: py + 15, width: cardW - 30, fontSize: 14, fontWeight: '700',
      fontFamily: 'Inter', fill: '#1f2328'
    });
    group.push(name);

    const role = new fabric.Textbox(p.role || 'Role', {
      left: px + 15, top: py + 38, width: cardW - 30, fontSize: 11, fontFamily: 'Inter',
      fill: resolveToken('{{brand.primary_color}}') || '#58a6ff'
    });
    group.push(role);

    if (p.pain_points && p.pain_points.length > 0) {
      p.pain_points.slice(0, 2).forEach((pp, j) => {
        const pain = new fabric.Textbox(`• ${pp}`, {
          left: px + 15, top: py + 60 + j * 22, width: cardW - 30, fontSize: 10,
          fontFamily: 'Inter', fill: '#656d76'
        });
        group.push(pain);
      });
    }
  });

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'persona_strip' };
  return g;
}

function renderProofBlock(zone, x, y, w, h) {
  const group = [];
  const bg = new fabric.Rect({ left: x, top: y, width: w, height: h, fill: resolveToken(zone.bg_color) || '#0f1117', rx: 8 });
  group.push(bg);

  if (zone.stat) {
    const stat = new fabric.Text(zone.stat, {
      left: x + w/2, top: y + h/2 - 20, fontSize: 56, fontWeight: '900',
      fontFamily: 'Inter', fill: '#ffffff', originX: 'center', originY: 'center'
    });
    group.push(stat);
  }

  if (zone.label) {
    const label = new fabric.Textbox(zone.label, {
      left: x + 20, top: y + h/2 + 25, width: w - 40, fontSize: 14, fontWeight: '500',
      fontFamily: 'Inter', fill: 'rgba(255,255,255,0.8)', textAlign: 'center'
    });
    group.push(label);
  }

  if (zone.quote) {
    const quote = new fabric.Textbox(`"${zone.quote}"`, {
      left: x + 40, top: y + h - 60, width: w - 80, fontSize: 12,
      fontFamily: 'Playfair Display', fill: 'rgba(255,255,255,0.7)', fontStyle: 'italic', textAlign: 'center'
    });
    group.push(quote);
  }

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'proof_block' };
  return g;
}

function renderCtaFooter(zone, x, y, w, h) {
  const group = [];
  const bg = new fabric.Rect({ left: x, top: y, width: w, height: h, fill: '#f6f8fa', stroke: '#d0d7de', strokeWidth: 1, rx: 8 });
  group.push(bg);

  const cta = new fabric.Rect({ left: x + w/2 - 100, top: y + 30, width: 200, height: 48, fill: resolveToken('{{brand.primary_color}}') || '#238636', rx: 24 });
  group.push(cta);

  const ctaText = new fabric.Text(zone.cta_text || 'Get Started', {
    left: x + w/2, top: y + 54, fontSize: 16, fontWeight: '600',
    fontFamily: 'Inter', fill: '#ffffff', originX: 'center', originY: 'center'
  });
  group.push(ctaText);

  if (zone.contact_name) {
    const contact = new fabric.Textbox(zone.contact_name, {
      left: x + 20, top: y + h - 30, width: w - 40, fontSize: 12, fontFamily: 'Inter',
      fill: '#656d76', textAlign: 'center'
    });
    group.push(contact);
  }

  // Logo
  const logoUrl = resolveToken(zone.logo_url) || '';
  if (logoUrl && logoUrl !== '{{brand.logo_url}}') {
    fabric.Image.fromURL(logoUrl, img => {
      img.set({ left: x + 20, top: y + h/2 - 15, width: 30, height: 30, selectable: true });
      canvas.add(img);
    });
  }

  const g = new fabric.Group(group, { left: x, top: y, selectable: true, evented: true });
  g.data = { zoneId: zone.id, zoneType: 'cta_footer' };
  return g;
}

function renderDefaultZone(zone, x, y, w, h) {
  const rect = new fabric.Rect({
    left: x, top: y, width: w, height: h, fill: 'rgba(88,166,255,0.1)',
    stroke: '#58a6ff', strokeWidth: 2, rx: 4, selectable: true, evented: true
  });
  const label = new fabric.Text(zone.type || 'unknown', {
    left: x + 10, top: y + 10, fontSize: 12, fill: '#58a6ff', fontWeight: '600'
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
