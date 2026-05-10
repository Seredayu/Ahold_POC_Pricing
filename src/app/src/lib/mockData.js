// Synthetic inventory items — Belgium Delhaize pilot (Bakery & Deli)
// hours_to_close = remaining shelf life hours (SLED proxy)
// sales_velocity_7d = units/day rolling 7d average

export const MOCK_ITEMS = [
  {
    item_id: 'SKU-001',
    name_fr: 'Fraises biologiques 500g',
    name_nl: 'Biologische aardbeien 500g',
    current_price: 3.49,
    stock: 17,
    hours_to_close: 6,
    sales_velocity_7d: 4.2,
  },
  {
    item_id: 'SKU-002',
    name_fr: 'Poulet rôti Label Rouge 1.2kg',
    name_nl: 'Geroosterde kip Label Rouge 1.2kg',
    current_price: 9.99,
    stock: 8,
    hours_to_close: 3,
    sales_velocity_7d: 2.8,
  },
  {
    item_id: 'SKU-003',
    name_fr: 'Croissants beurre x6',
    name_nl: 'Boter croissants x6',
    current_price: 2.89,
    stock: 24,
    hours_to_close: 5,
    sales_velocity_7d: 9.1,
  },
  {
    item_id: 'SKU-004',
    name_fr: 'Saumon fumé 200g',
    name_nl: 'Gerookte zalm 200g',
    current_price: 5.99,
    stock: 12,
    hours_to_close: 7,
    sales_velocity_7d: 3.4,
  },
  {
    item_id: 'SKU-005',
    name_fr: 'Aardbeien biologisch gewassen 500g klasse II Delhaize',
    name_nl: 'Aardbeien biologisch gewassen 500g klasse II Delhaize',
    current_price: 2.49,
    stock: 31,
    hours_to_close: 4,
    sales_velocity_7d: 11.6,
  },
]
