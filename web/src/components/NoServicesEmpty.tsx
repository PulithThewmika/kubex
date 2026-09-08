import { IllustratedEmpty } from './IllustratedEmpty'

export function NoServicesEmpty({ variant = 'center' }: { variant?: 'center' | 'split' }) {
  return (
    <IllustratedEmpty
      variant={variant}
      image="/Noservice.png"
      title="No services yet"
      lines={[
        'Services appear here once a deployment webhook fires.',
        'Install the KubeX GitHub App on your org — webhooks for every workflow run are provisioned automatically, no secrets to copy.',
        'Drop the lightweight agent into your cluster so KubeX sees deploy events and pod health over an outbound connection.',
        'Every deploy then gets a health score, a DORA trend, and an alert if it made things worse.',
      ]}
      action={{ to: '/app/settings?tab=connections', label: 'Connect a repository' }}
    />
  )
}
