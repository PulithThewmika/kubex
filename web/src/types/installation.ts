export type Installation = {
  id: string
  account_login: string
  repos: string[]
  status: 'active' | 'suspended' | 'removed'
  created_at: string
}
