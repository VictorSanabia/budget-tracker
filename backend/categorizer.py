CATEGORIES = {
    'Groceries': ['walmart', 'target', 'kroger', 'aldi', 'whole foods', 'trader joe', 'costco', 'sam\'s club', 'publix', 'safeway', 'heb', 'meijer', 'food', 'grocery', 'market'],
    'Dining': ['restaurant', 'mcdonald', 'starbucks', 'chipotle', 'subway', 'pizza', 'burger', 'taco', 'doordash', 'uber eats', 'grubhub', 'chick-fil', 'panera', 'domino', 'wendy', 'diner', 'cafe', 'coffee', 'sushi', 'grill', 'kitchen', 'eatery'],
    'Gas & Fuel': ['shell', 'exxon', 'bp', 'chevron', 'mobil', 'sunoco', 'marathon', 'citgo', 'fuel', 'gas station', 'speedway', 'kwik', 'casey'],
    'Transportation': ['uber', 'lyft', 'parking', 'toll', 'transit', 'metro', 'bus', 'train', 'airline', 'delta', 'american air', 'southwest', 'united air'],
    'Shopping': ['amazon', 'ebay', 'etsy', 'best buy', 'home depot', 'lowes', 'ikea', 'nordstrom', 'macy', 'gap', 'old navy', 'h&m', 'zara', 'apple store', 'nike', 'ross', 'tj maxx', 'marshalls'],
    'Subscriptions': ['netflix', 'spotify', 'hulu', 'disney', 'hbo', 'apple', 'google', 'microsoft', 'adobe', 'dropbox', 'subscription', 'membership', 'prime', 'peacock', 'paramount'],
    'Utilities': ['electric', 'water', 'gas bill', 'internet', 'comcast', 'att', 'verizon', 't-mobile', 'xfinity', 'spectrum', 'utility', 'power', 'energy', 'sewage', 'waste'],
    'Healthcare': ['pharmacy', 'cvs', 'walgreens', 'rite aid', 'doctor', 'hospital', 'clinic', 'dental', 'vision', 'medical', 'health', 'lab', 'urgent care', 'insurance'],
    'Entertainment': ['movie', 'cinema', 'amc', 'regal', 'game', 'steam', 'playstation', 'xbox', 'nintendo', 'ticketmaster', 'concert', 'event', 'museum', 'zoo', 'bowling', 'golf'],
    'Travel': ['hotel', 'airbnb', 'marriott', 'hilton', 'hyatt', 'expedia', 'booking', 'resort', 'vrbo', 'motel'],
    'Personal Care': ['salon', 'barber', 'spa', 'nail', 'beauty', 'haircut', 'massage', 'sephora', 'ulta'],
    'Education': ['tuition', 'school', 'university', 'college', 'course', 'udemy', 'coursera', 'book', 'textbook'],
    'Income': ['direct deposit', 'payroll', 'zelle', 'transfer from', 'deposit', 'refund'],
    'Transfer': ['transfer', 'payment to', 'payment from', 'zelle', 'venmo', 'paypal', 'cash app'],
}

def categorize(description: str) -> str:
    desc_lower = description.lower()
    for category, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in desc_lower:
                return category
    return 'Other'
