/**
 * Application configuration
 */

const getApiPrefix = () => {
  const meta = document.querySelector('meta[name="api-prefix"]');
  return meta ? meta.content : '';
};

export const apiUrl = (path) => {
  const prefix = getApiPrefix();
  if (prefix && path.startsWith('/')) {
    return prefix + path;
  }
  return prefix + (path.startsWith('/') ? '' : '/') + path;
};

window.apiUrl = apiUrl;
export const config = {
  apiUrl,
};