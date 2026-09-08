export type Installation = {
  id: string
  github_installation_id: number
  account_login: string
  repos: string[]
  status: 'active' | 'suspended' | 'removed'
  created_at: string
}
