export const categories = {
 Network: 'Network and Connectivity', 'Classroom Technology': 'Classroom Technology and AV',
 Hardware: 'Hardware', Software: 'Software and Applications', Account: 'Account and Access',
 'Printing and Scanning': 'Printing and Scanning', Security: 'Cybersecurity',
 'Email and Collaboration': 'Email and Collaboration', Other: 'Other',
};
export const statuses = ['Open', 'Investigating', 'Resolved'];
export const json = (method, data) => ({method, body: JSON.stringify(data)});
export {formatTime, priorityName} from './dashboard';
