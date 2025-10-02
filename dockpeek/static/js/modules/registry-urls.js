export function getRegistryUrl(imageName) {
  if (!imageName) return null;

  const withoutTag = imageName.split(':')[0];
  const parts = withoutTag.split('/');

  if (parts.length <= 2 && (parts.length === 1 || !parts[0].includes('.'))) {
    const namespace = parts.length === 2 ? parts[0] : 'library';
    const repo = parts[parts.length - 1];
    return `https://hub.docker.com/r/${namespace}/${repo}`;
  }

  const registryHost = parts[0];
  const repoPath = parts.slice(1).join('/');

  switch (registryHost) {
    case 'lscr.io':
      return `https://github.com/${parts[1]}/docker-${parts.slice(2).join('%2F')}/pkgs/container/${parts.slice(2).join('%2F')}`;

    case 'ghcr.io':
      const ghcrUser = parts[1];
      const ghcrRepo = parts.slice(2).join('/');
      return `https://github.com/${ghcrUser}/${ghcrRepo}/pkgs/container/${ghcrRepo}`;

    case 'quay.io':
      return `https://quay.io/repository/${repoPath}`;

    case 'public.ecr.aws':
      return `https://gallery.ecr.aws/${parts[1]}/${parts.slice(2).join('/')}`;

    case 'registry.gitlab.com':
      return `https://gitlab.com/${parts[1]}/${parts[2]}/container_registry`;

    default:
      return null;
  }
}
