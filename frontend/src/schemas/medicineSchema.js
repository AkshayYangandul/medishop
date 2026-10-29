import { z } from 'zod';

export const medicineSchema = z.object({
  name: z.string().min(2, 'Medicine name must have at least 2 characters'),
  genericName: z.string().optional(),
  categoryId: z.string().min(1, 'Category is required'),
  brandId: z.string().min(1, 'Brand is required'),
  dosageForm: z.enum(['Tablet', 'Capsule', 'Syrup', 'Injection', 'Ointment', 'Drops', 'Inhaler', 'Other']),
  strength: z.string().optional(),
  unitPrice: z.coerce.number().positive('Unit price must be positive'),
  mrp: z.coerce.number().positive('MRP must be positive'),
  minStockAlert: z.coerce.number().int().nonnegative('Minimum stock alert must be 0 or higher'),
  requiresPrescription: z.boolean().default(false),
});
