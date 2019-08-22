import datetime as dt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def balance_graph(balance_histories):

    x = [history.date_created for history in balance_histories] 
    y = [history.balance for history in balance_histories] 

    fig, ax = plt.subplots()
    ax.set_ylabel('balance')
    ax.set_title('Balance History')
    ax.plot(x, y, markerfacecolor='CornflowerBlue', markeredgecolor='white')
    fig.autofmt_xdate()

    return fig.savefig("tmp/balance.png")

