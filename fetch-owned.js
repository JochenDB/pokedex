/*
 * fetch-owned.js — rebuild owned.json from Collectr
 * =================================================
 *
 * WHY THE OLD TRICK BROKE
 * -----------------------
 * The portfolio no longer uses the public showcase endpoint
 *     https://api-v2.getcollectr.com/data/showcase/<showcaseId>?...
 * It now loads your collection from an AUTHENTICATED endpoint
 *     GET https://api-v2.getcollectr.com/collections/<accountId>/products
 * which requires an `Authorization` header. Pasting the URL in the browser
 * (no auth header) => 401 "Unauthorized Request".
 *
 * The token lives in localStorage / cookie under the key `collectrToken`, but
 * it is stored as a JSON WRAPPER, not a raw token:
 *     {"username":"<accountId>","token":"<the JWT you actually need>"}
 * You must send the inner `.token` value (a ~179-char JWT) as the
 * Authorization header, WITHOUT a "Bearer " prefix. Sending the whole JSON
 * blob (or the raw cookie string) is what fails with 401.
 *
 * HOW TO USE
 * ----------
 * 1. Log in at https://app.getcollectr.com and open /portfolio/products
 * 2. Open DevTools (F12) -> Console
 * 3. Paste the whole snippet below (or call collectrDownloadOwned()) and Enter
 * 4. owned.json downloads; move it into this repo.
 *
 * The token is refreshed by the app while you are logged in, so just re-run
 * this whenever you want fresh data. If you ever get a 401, reload the
 * portfolio page (or log in again) so a fresh token is written to storage.
 *
 * Response shape of the products endpoint:
 *   { value: [{price, insertion_date}],   // portfolio value graph -> portfolio_value
 *     data:  [ ...one entry per product ], // -> products
 *     filters: [...] }
 */

async function collectrBuildOwned({ collectionId } = {}) {
  const stored = JSON.parse(localStorage.getItem('collectrToken'));
  const token = stored.token;                 // inner JWT — this is the important bit
  const acct  = stored.username;              // your account id (== default collection id)
  const id    = collectionId || acct;         // default "Main" collection; pass another id to switch
  const H = { Accept: 'application/json, text/plain, */*', Authorization: token };
  const get = async (p) => {
    const r = await fetch(`https://api-v2.getcollectr.com${p}`, { headers: H });
    if (!r.ok) throw new Error(`${p} -> HTTP ${r.status} (token expired? reload the portfolio page)`);
    return r.json();
  };

  const acc  = await get(`/accounts/${acct}`);
  const cols = await get(`/accounts/${acct}/collections`);
  const colsArr = Array.isArray(cols) ? cols : (cols.data || cols.value || cols.collections || []);
  const prod = await get(`/collections/${id}/products?offset=0&limit=5000&unstackedView=true&currency=USD&filters=`);

  const products = (prod.data || []).map((p) => ({
    product_id: p.product_id,
    catalog_category_name: p.catalog_category_name,
    catalog_group: p.catalog_group,
    catalog_group_id: p.catalog_group_id,
    product_name: p.product_name,
    image_url: p.image_url,
    card_number: p.card_number,
    rarity: p.rarity,
    quantity: p.quantity,
    grade_id: p.grade_id,
    market_price: p.market_price,
    market_price_diff: p.market_price_diff,
    market_price_percentage_diff: p.market_price_percentage_diff,
    total_products_owned_count: p.total_products_owned_count,
  }));

  return {
    user: acc.given_name,
    showcaseEnabled: acc.portfolio_sharing_enabled,
    handle: acc.handle,
    collections: colsArr.map((c) => ({
      id: c.id || c.collection_id,
      name: c.name || c.collection_name,
      default: c.default ?? c.is_default,
    })),
    profile_photo: acc.profile_photo_url,
    total_cards: acc.total_cards,
    total_sealed: acc.total_sealed,
    total_graded: acc.total_graded,
    total_followers: acc.total_followers,
    total_following: acc.total_following,
    total_posts: acc.total_posts,
    portfolio_value: prod.value || [],
    products,
  };
}

async function collectrDownloadOwned(opts) {
  const owned = await collectrBuildOwned(opts);
  const blob = new Blob([JSON.stringify(owned, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'owned.json';
  a.click();
  URL.revokeObjectURL(a.href);
  console.log(`owned.json downloaded — ${owned.products.length} products`);
  return owned;
}

// Auto-run when pasted into the console:
collectrDownloadOwned();
