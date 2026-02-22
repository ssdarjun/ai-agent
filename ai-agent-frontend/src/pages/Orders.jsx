import { useState, useEffect } from 'react';

function Orders() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8000/orders')
      .then((response) => response.json())
      .then((data) => {
        setOrders(data.orders);
        setLoading(false);
      })
      .catch((error) => {
        console.error('Error fetching orders:', error);
        setLoading(false);
      });
  }, []);

  return (
    <div className="bg-gray-50 min-h-screen py-16">
      <div className="container mx-auto px-4">
        <div className="mb-12 text-left">
          <h1 className="text-4xl font-black text-gray-900 mb-2">Order History</h1>
          <p className="text-gray-500">Track and manage all your recent orders.</p>
        </div>

        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-100">
                    <th className="px-6 py-4 text-sm font-bold text-gray-600 uppercase tracking-wider">Order ID</th>
                    <th className="px-6 py-4 text-sm font-bold text-gray-600 uppercase tracking-wider">Product</th>
                    <th className="px-6 py-4 text-sm font-bold text-gray-600 uppercase tracking-wider">Qty</th>
                    <th className="px-6 py-4 text-sm font-bold text-gray-600 uppercase tracking-wider">Customer Info</th>
                    <th className="px-6 py-4 text-sm font-bold text-gray-600 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-4 text-sm font-bold text-gray-600 uppercase tracking-wider">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {orders.length > 0 ? (
                    orders.map((order) => (
                      <tr key={order.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-6 py-4 text-sm font-medium text-blue-600">{order.id}</td>
                        <td className="px-6 py-4 text-sm text-gray-800 font-semibold">{order.product_title}</td>
                        <td className="px-6 py-4 text-sm text-gray-600">{order.quantity}</td>
                        <td className="px-6 py-4 text-sm text-gray-600">
                          <div className="font-medium text-gray-800">{order.customer_phone}</div>
                          <div className="text-xs text-gray-400 line-clamp-1">{order.address}</div>
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-tighter ${
                            order.status === 'pending' ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'
                          }`}>
                            {order.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-500 whitespace-nowrap">
                          {new Date(order.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="6" className="px-6 py-20 text-center text-gray-500">
                        No orders found. Start shopping to see your history!
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default Orders;
