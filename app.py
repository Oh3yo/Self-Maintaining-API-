import payments


def checkout(cart):
    total = sum(i.price for i in cart)
    return payments.charge(total, "USD")